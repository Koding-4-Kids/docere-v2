"""Instructor dashboard endpoints."""

import uuid
from collections import defaultdict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import or_, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from docere.config import settings
from docere.core.classroom_agent import ClassroomAgent, _confusion_label, _mastery_label
from docere.core.knowledge_tracing import BKTParams, bkt_update, confusion_to_correct
from docere.core.memory.concept_utils import normalize_concept
from docere.dependencies import get_db, get_claude, get_qdrant, require_instructor
from docere.integrations.llm.client import ClaudeClient
from docere.integrations.vector_db.qdrant import QdrantStore
from docere.models.calendar import InstructorCalendarToken
from docere.models.course import Course, Enrollment
from docere.models.memory import ConceptMastery, MemoryRecord, StudentProfile
from docere.models.strategy import Strategy

router = APIRouter()


class DashboardSummaryResponse(BaseModel):
    course_id: str
    course_name: str
    student_count: int

    model_config = {"from_attributes": True}


@router.get("/dashboard/{course_id}/summary", response_model=DashboardSummaryResponse)
async def get_dashboard_summary(
    course_id: uuid.UUID,
    user_id: uuid.UUID = Depends(require_instructor),
    db: AsyncSession = Depends(get_db),
) -> DashboardSummaryResponse:
    """Minimal dashboard data: course name + enrolled student count."""
    course = await db.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    result = await db.execute(
        select(func.count(Enrollment.id)).where(
            Enrollment.course_id == course_id,
            Enrollment.lms_role == "student",
        )
    )
    student_count = result.scalar() or 0

    return DashboardSummaryResponse(
        course_id=str(course.id),
        course_name=course.name,
        student_count=student_count,
    )


class GraphNode(BaseModel):
    id: str
    name: str
    type: str  # "student", "memory", or "concept"
    # Student fields
    engagement: str | None = None
    total_interactions: int | None = None
    avg_confusion: float | None = None
    # Memory fields
    memory_type: str | None = None
    content: str | None = None
    concepts: list[str] | None = None
    confusion_score: float | None = None
    sentiment: str | None = None
    # Concept fields
    avg_mastery: float | None = None
    student_count: int | None = None
    times_struggled: int | None = None
    mastery_label: str | None = None


class GraphEdge(BaseModel):
    source: str
    target: str
    type: str  # "student_memory", "shared_concept", "concept_student", "concept_concept"
    weight: float | None = None


class StudentMemoryGraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


@router.get("/dashboard/{course_id}/concept-graph", response_model=StudentMemoryGraphResponse)
async def get_student_memory_graph(
    course_id: uuid.UUID,
    topology: str = "student",
    user_id: uuid.UUID = Depends(require_instructor),
    db: AsyncSession = Depends(get_db),
) -> StudentMemoryGraphResponse:
    """Graph data with topology modes: student (hub), concept (hub), distributed (flat)."""
    from docere.models.user import User

    if topology == "concept":
        return await _build_concept_graph(course_id, db)

    # ── Student-centric + distributed share the same data ──

    # 1. Get enrolled students with their profiles
    result = await db.execute(
        select(User.id, User.name, StudentProfile)
        .join(Enrollment, Enrollment.user_id == User.id)
        .outerjoin(
            StudentProfile,
            (StudentProfile.student_id == User.id)
            & (StudentProfile.course_id == course_id),
        )
        .where(
            Enrollment.course_id == course_id,
            Enrollment.lms_role == "student",
        )
    )
    students = result.all()

    if not students:
        return StudentMemoryGraphResponse(nodes=[], edges=[])

    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    student_ids = []

    for user_id_val, user_name, profile in students:
        sid = str(user_id_val)
        student_ids.append(user_id_val)
        nodes.append(GraphNode(
            id=sid,
            name=user_name,
            type="student",
            engagement=profile.engagement_level if profile else "unknown",
            total_interactions=profile.total_interactions if profile else 0,
            avg_confusion=round(profile.avg_confusion_score, 2) if profile else 0.0,
        ))

    # 2. Get recent memories for these students (cap at 20 per student)
    if student_ids:
        mem_result = await db.execute(
            select(MemoryRecord)
            .where(
                MemoryRecord.course_id == course_id,
                MemoryRecord.student_id.in_(student_ids),
                MemoryRecord.is_compressed.is_(False),
            )
            .order_by(MemoryRecord.created_at.desc())
            .limit(len(student_ids) * 20)
        )
        memories = mem_result.scalars().all()

        # Track concept → memory IDs for shared-concept edges
        concept_to_mems: dict[str, list[str]] = defaultdict(list)

        for mem in memories:
            mid = f"mem_{mem.id}"
            short_content = (mem.content[:120] + "...") if len(mem.content) > 120 else mem.content
            nodes.append(GraphNode(
                id=mid,
                name=short_content,
                type="memory",
                memory_type=mem.memory_type,
                content=short_content,
                concepts=mem.concepts,
                confusion_score=round(mem.confusion_score, 2) if mem.confusion_score else 0.0,
                sentiment=mem.sentiment,
            ))
            edges.append(GraphEdge(
                source=str(mem.student_id),
                target=mid,
                type="student_memory",
            ))
            if mem.concepts:
                for concept in mem.concepts:
                    concept_to_mems[concept].append(mid)

        # 3. Build shared-concept edges (memories that share a concept)
        for concept, mem_ids in concept_to_mems.items():
            if len(mem_ids) < 2:
                continue
            for i in range(min(len(mem_ids), 5)):
                for j in range(i + 1, min(len(mem_ids), 5)):
                    edges.append(GraphEdge(
                        source=mem_ids[i],
                        target=mem_ids[j],
                        type="shared_concept",
                    ))

    return StudentMemoryGraphResponse(nodes=nodes, edges=edges)


async def _build_concept_graph(
    course_id: uuid.UUID,
    db: AsyncSession,
) -> StudentMemoryGraphResponse:
    """Concept-centric topology: concepts as hubs, students orbit around them."""
    from docere.models.user import User

    # 1. Get concept aggregates
    concept_result = await db.execute(
        select(
            ConceptMastery.concept_name,
            func.avg(ConceptMastery.mastery_level).label("avg_mastery"),
            func.sum(ConceptMastery.times_struggled).label("total_struggled"),
            func.count(ConceptMastery.student_id.distinct()).label("student_count"),
        )
        .where(ConceptMastery.course_id == course_id)
        .group_by(ConceptMastery.concept_name)
        .order_by(func.count(ConceptMastery.student_id.distinct()).desc())
        .limit(25)
    )
    concept_rows = concept_result.all()

    if not concept_rows:
        return StudentMemoryGraphResponse(nodes=[], edges=[])

    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    concept_names = []

    for row in concept_rows:
        cid = f"concept_{row.concept_name}"
        avg_m = float(row.avg_mastery)
        nodes.append(GraphNode(
            id=cid,
            name=row.concept_name,
            type="concept",
            avg_mastery=round(avg_m, 2),
            student_count=int(row.student_count),
            times_struggled=int(row.total_struggled),
            mastery_label=_mastery_label(avg_m),
        ))
        concept_names.append(row.concept_name)

    # 2. Get per-student mastery for these concepts
    mastery_result = await db.execute(
        select(ConceptMastery.student_id, ConceptMastery.concept_name, ConceptMastery.mastery_level)
        .where(
            ConceptMastery.course_id == course_id,
            ConceptMastery.concept_name.in_(concept_names),
        )
    )
    mastery_rows = mastery_result.all()

    # 3. Get student names
    student_ids_in_graph = list({str(r.student_id) for r in mastery_rows})
    if student_ids_in_graph:
        students_result = await db.execute(
            select(User.id, User.name, StudentProfile)
            .outerjoin(
                StudentProfile,
                (StudentProfile.student_id == User.id)
                & (StudentProfile.course_id == course_id),
            )
            .where(User.id.in_(student_ids_in_graph))
        )
        for uid, uname, profile in students_result.all():
            nodes.append(GraphNode(
                id=str(uid),
                name=uname,
                type="student",
                engagement=profile.engagement_level if profile else "unknown",
                total_interactions=profile.total_interactions if profile else 0,
                avg_confusion=round(profile.avg_confusion_score, 2) if profile else 0.0,
            ))

    # 4. Build concept → student edges
    for row in mastery_rows:
        edges.append(GraphEdge(
            source=f"concept_{row.concept_name}",
            target=str(row.student_id),
            type="concept_student",
            weight=round(float(row.mastery_level), 2),
        ))

    # 5. Build concept → concept edges (co-occurrence: shared students)
    concept_students: dict[str, set[str]] = defaultdict(set)
    for row in mastery_rows:
        concept_students[row.concept_name].add(str(row.student_id))

    concept_list = list(concept_students.keys())
    for i in range(len(concept_list)):
        for j in range(i + 1, len(concept_list)):
            shared = concept_students[concept_list[i]] & concept_students[concept_list[j]]
            if len(shared) >= 2:
                edges.append(GraphEdge(
                    source=f"concept_{concept_list[i]}",
                    target=f"concept_{concept_list[j]}",
                    type="concept_concept",
                    weight=len(shared) / max(
                        len(concept_students[concept_list[i]]),
                        len(concept_students[concept_list[j]]),
                    ),
                ))

    return StudentMemoryGraphResponse(nodes=nodes, edges=edges)


# ── Meta Command Center ──


class MetaQueryRequest(BaseModel):
    question: str
    history: list[dict[str, str]] = []


class CourseSummaryItem(BaseModel):
    course_id: str
    course_name: str
    student_count: int
    engagement_breakdown: dict[str, int]
    avg_confusion: float
    top_struggles: list[str]


class MetaQueryResponse(BaseModel):
    answer: str
    course_summaries: list[CourseSummaryItem] = []
    actions: list[dict] = []


META_SYSTEM_PROMPT = """You are an AI teaching assistant acting as an instructor's Command Center.
You have access to aggregated data from ALL of the instructor's classrooms.

Your job is to help the instructor:
- See trends across all their courses at a glance
- Identify which classes or students need the most attention
- Generate content (slides, notes, reports, discussion prompts, worksheets)
- Plan interventions across multiple classes
- Prepare for office hours, meetings, or parent/admin reports

Guidelines:
- Keep responses concise (4-8 sentences for analysis, longer for generated content).
- NEVER use markdown bold (**) or headers (###). Write in plain conversational sentences.
- NEVER output raw numbers or decimals. Use teacher-friendly language.
- When comparing courses, be specific about which class and why.
- When generating content (slides, notes, reports), use clear structure but keep it practical.
- If the instructor asks for something you need more context on, ask a clarifying question.
- End analysis responses with one concrete suggestion the teacher can act on today.

When generating slides, use this format:
---
SLIDE 1: [Title]
[Content — 3-5 bullet points max]

SLIDE 2: [Title]
[Content]
---

When generating meeting prep or reports, use clear sections but plain language."""

INTEGRATION_ACTIONS_PROMPT = """
## Available Actions

You can suggest actions for the instructor to execute. When an action is appropriate,
include an action block at the END of your response (after your conversational text).

IMPORTANT RULES:
- Only suggest actions for CONNECTED integrations listed below.
- NEVER auto-execute. Always explain what the action will do first.
- Include your conversational response BEFORE the action block.
- Only include ONE action block per response.
- Only suggest an action when the instructor explicitly asks for one (e.g. "email", "create a doc", "post announcement").

{available_actions}

Action block format — include at the end of your response when appropriate:

```action
{{"type": "action_type", ...payload fields...}}
```
"""


def _build_integration_prompt(
    google_connected: bool,
    google_scopes: str,
    lms_connected: bool,
    lms_type: str | None,
    course_context: list[tuple[str, str, str]],
) -> str:
    """Build the integration instructions section for the system prompt.

    course_context: list of (course_name, external_lms_id, course_id) tuples.
    """
    available: list[str] = []

    if google_connected:
        if "gmail" in google_scopes:
            available.append(
                '- **draft_email**: Send email. Payload: {"type": "draft_email", "to": ["email@example.com"], "subject": "Subject", "body": "HTML body"}'
            )
        if "docs" in google_scopes or "documents" in google_scopes:
            available.append(
                '- **create_doc**: Create a Google Doc. Payload: {"type": "create_doc", "title": "Title", "content": "Document content"}'
            )
        if "sheets" in google_scopes or "spreadsheets" in google_scopes:
            available.append(
                '- **create_sheet**: Create a Google Sheet. Payload: {"type": "create_sheet", "title": "Title", "headers": ["Col1", "Col2"], "rows": [["val1", "val2"]]}'
            )
        available.append(
            '- **calendar_event**: Create a calendar event. Payload: {"type": "calendar_event", "summary": "Event", "description": "Details", "start": "2026-02-20T14:00:00", "end": "2026-02-20T15:00:00"}'
        )

    if lms_connected and lms_type and course_context:
        lms_label = lms_type.capitalize()
        course_ids_str = ", ".join(
            f'"{name}" (LMS ID: {ext_id})'
            for name, ext_id, _ in course_context
            if ext_id
        )
        available.append(
            f'- **lms_announcement**: Post announcement to {lms_label}. '
            f'Use one of these course IDs: {course_ids_str}. '
            f'Payload: {{"type": "lms_announcement", "course_id": "LMS_COURSE_ID", "title": "Title", "message": "Body HTML"}}'
        )

    if not available:
        return ""

    actions_text = "\n".join(available)
    return INTEGRATION_ACTIONS_PROMPT.format(available_actions=actions_text)


@router.post("/meta/query", response_model=MetaQueryResponse)
async def meta_query(
    request: MetaQueryRequest,
    user_id: uuid.UUID = Depends(require_instructor),
    db: AsyncSession = Depends(get_db),
    claude: ClaudeClient = Depends(get_claude),
) -> MetaQueryResponse:
    """Cross-classroom query for the instructor Command Center."""
    from docere.models.user import User

    # 1. Get all courses where this user is an instructor/TA
    courses_result = await db.execute(
        select(Course.id, Course.name, Course.external_lms_id)
        .join(Enrollment, Enrollment.course_id == Course.id)
        .where(
            Enrollment.user_id == user_id,
            Enrollment.lms_role.in_(["teacher", "instructor", "ta", "admin"]),
        )
    )
    courses = courses_result.all()

    if not courses:
        return MetaQueryResponse(answer="You don't have any courses yet. Add Docere to a course in your LMS to get started.")

    course_ids = [c.id for c in courses]
    course_names = {str(c.id): c.name for c in courses}
    course_lms_ids = {str(c.id): (c.external_lms_id or "") for c in courses}

    # 2. Per-course student counts + engagement
    enrollment_result = await db.execute(
        select(
            Enrollment.course_id,
            func.count(Enrollment.id).label("student_count"),
        )
        .where(
            Enrollment.course_id.in_(course_ids),
            Enrollment.lms_role == "student",
        )
        .group_by(Enrollment.course_id)
    )
    enrollment_counts = {str(r.course_id): r.student_count for r in enrollment_result.all()}

    # 3. Per-course engagement breakdown + avg confusion
    profile_result = await db.execute(
        select(
            StudentProfile.course_id,
            StudentProfile.engagement_level,
            func.count(StudentProfile.id).label("cnt"),
            func.avg(StudentProfile.avg_confusion_score).label("avg_confusion"),
        )
        .where(StudentProfile.course_id.in_(course_ids))
        .group_by(StudentProfile.course_id, StudentProfile.engagement_level)
    )
    engagement_by_course: dict[str, dict[str, int]] = defaultdict(dict)
    confusion_by_course: dict[str, list[float]] = defaultdict(list)
    for r in profile_result.all():
        cid = str(r.course_id)
        engagement_by_course[cid][r.engagement_level or "unknown"] = r.cnt
        if r.avg_confusion is not None:
            confusion_by_course[cid].append(float(r.avg_confusion))

    # 4. Per-course top struggled concepts
    concept_result = await db.execute(
        select(
            ConceptMastery.course_id,
            ConceptMastery.concept_name,
            func.sum(ConceptMastery.times_struggled).label("total_struggled"),
        )
        .where(ConceptMastery.course_id.in_(course_ids))
        .group_by(ConceptMastery.course_id, ConceptMastery.concept_name)
        .order_by(func.sum(ConceptMastery.times_struggled).desc())
    )
    struggles_by_course: dict[str, list[str]] = defaultdict(list)
    for r in concept_result.all():
        cid = str(r.course_id)
        if len(struggles_by_course[cid]) < 5:
            struggles_by_course[cid].append(r.concept_name)

    # 5. Build course summaries
    course_summaries: list[CourseSummaryItem] = []
    context_lines: list[str] = []

    for course in courses:
        cid = str(course.id)
        student_count = enrollment_counts.get(cid, 0)
        engagement = engagement_by_course.get(cid, {})
        confusion_vals = confusion_by_course.get(cid, [])
        avg_conf = sum(confusion_vals) / len(confusion_vals) if confusion_vals else 0.0
        top_struggles = struggles_by_course.get(cid, [])

        summary = CourseSummaryItem(
            course_id=cid,
            course_name=course.name,
            student_count=student_count,
            engagement_breakdown=engagement,
            avg_confusion=round(avg_conf, 2),
            top_struggles=top_struggles,
        )
        course_summaries.append(summary)

        # Build context string for LLM
        eng_parts = []
        for level in ("high", "medium", "low", "inactive"):
            n = engagement.get(level, 0)
            if n > 0:
                eng_parts.append(f"{n} {level}")
        eng_str = ", ".join(eng_parts) if eng_parts else "no engagement data"
        conf_label = _confusion_label(avg_conf) if confusion_vals else "no data"
        struggles_str = ", ".join(top_struggles[:3]) if top_struggles else "none tracked"

        context_lines.append(
            f"• {course.name}: {student_count} students | "
            f"Engagement: {eng_str} | "
            f"Overall comfort: {conf_label} | "
            f"Top struggles: {struggles_str}"
        )

    # 6. Check integration status for tool-aware prompting
    token_result = await db.execute(
        select(InstructorCalendarToken).where(
            InstructorCalendarToken.instructor_id == user_id,
            InstructorCalendarToken.is_active == True,  # noqa: E712
        )
    )
    google_token = token_result.scalar_one_or_none()
    google_connected = google_token is not None
    google_scopes = google_token.scopes if google_token else ""

    lms_connected = bool(settings.moodle_base_url and settings.moodle_api_token) or \
                    bool(settings.canvas_base_url and settings.canvas_api_token)
    lms_type = "moodle" if settings.moodle_base_url else ("canvas" if settings.canvas_base_url else None)

    course_context = [
        (c.name, course_lms_ids.get(str(c.id), ""), str(c.id))
        for c in courses
    ]
    integration_instructions = _build_integration_prompt(
        google_connected=google_connected,
        google_scopes=google_scopes,
        lms_connected=lms_connected,
        lms_type=lms_type,
        course_context=course_context,
    )

    # 7. Build system prompt with cross-classroom context
    system_prompt = (
        f"{META_SYSTEM_PROMPT}\n\n"
        f"{integration_instructions}\n\n"
        f"## Instructor's Courses ({len(courses)} total)\n"
        f"{chr(10).join(context_lines)}"
    )

    messages = [*request.history[-10:], {"role": "user", "content": request.question}]
    text = await claude.chat(
        system_prompt=system_prompt,
        messages=messages,
        max_tokens=1200,
        temperature=0.4,
    )

    # 8. Parse action blocks from LLM response
    from docere.core.action_parser import extract_actions
    clean_text, actions = extract_actions(text)

    return MetaQueryResponse(answer=clean_text, course_summaries=course_summaries, actions=actions)


@router.get("/alerts")
async def get_alerts() -> dict[str, str]:
    """Get alerts filterable by course, severity, read status."""
    # TODO: Return paginated alerts
    return {"status": "not_implemented"}


@router.patch("/alerts/{alert_id}")
async def update_alert(alert_id: str) -> dict[str, str]:
    """Mark alert as read/resolved."""
    # TODO: Update alert status
    return {"status": "not_implemented"}


@router.get("/dashboard/{course_id}")
async def get_dashboard(course_id: str) -> dict[str, str]:
    """Get aggregated class analytics for instructor dashboard."""
    # TODO: Return class-wide metrics, engagement, performance overview
    return {"status": "not_implemented"}


@router.get("/dashboard/{course_id}/at-risk")
async def get_at_risk_students(course_id: str) -> dict[str, str]:
    """Get list of at-risk students with evidence."""
    # TODO: Return students flagged by analysis, with reasons and recommended actions
    return {"status": "not_implemented"}


@router.get("/dashboard/{course_id}/patterns")
async def get_class_patterns(course_id: str) -> dict[str, str]:
    """Get class-wide struggle patterns."""
    # TODO: Return common concepts students struggle with, trending issues
    return {"status": "not_implemented"}


# ── Instructor Memory Query ──

class SourceFilterConfig(BaseModel):
    """Teacher-controlled data source filters."""
    profiles: bool = True   # student engagement, confusion, grades
    mastery: bool = True    # per-concept mastery (BKT)


class InstructorQueryRequest(BaseModel):
    question: str
    history: list[dict[str, str]] = []  # prior chat turns
    source_filters: SourceFilterConfig | None = None


class SourceRefResponse(BaseModel):
    type: str
    label: str
    student_name: str | None = None
    detail: str | None = None


class InstructorQueryResponse(BaseModel):
    answer: str
    widgets: list[dict] = []
    sources: list[SourceRefResponse] = []


@router.post("/dashboard/{course_id}/query", response_model=InstructorQueryResponse)
async def query_memory_layer(
    course_id: uuid.UUID,
    request: InstructorQueryRequest,
    user_id: uuid.UUID = Depends(require_instructor),
    db: AsyncSession = Depends(get_db),
    qdrant: QdrantStore = Depends(get_qdrant),
    claude: ClaudeClient = Depends(get_claude),
) -> InstructorQueryResponse:
    """Query the classroom agent about students via natural language."""
    agent = ClassroomAgent(db=db, qdrant=qdrant, claude=claude)
    history = [
        {"role": t.get("role", "user"), "content": t.get("content", "")}
        for t in request.history[-10:]
    ]
    filters = request.source_filters.model_dump() if request.source_filters else None
    response = await agent.answer(
        course_id=str(course_id),
        question=request.question,
        history=history,
        source_filters=filters,
    )
    return InstructorQueryResponse(
        answer=response.text,
        widgets=response.widgets,
        sources=[
            SourceRefResponse(
                type=s.type,
                label=s.label,
                student_name=s.student_name,
                detail=s.detail,
            )
            for s in response.sources
        ],
    )


# ── Add Concept ──


class AddConceptRequest(BaseModel):
    concept_name: str = Field(..., min_length=1, max_length=255)


class AddConceptResponse(BaseModel):
    cell: dict
    students_affected: int
    memories_matched: int


@router.post("/dashboard/{course_id}/concepts", response_model=AddConceptResponse)
async def add_concept(
    course_id: uuid.UUID,
    request: AddConceptRequest,
    user_id: uuid.UUID = Depends(require_instructor),
    db: AsyncSession = Depends(get_db),
) -> AddConceptResponse:
    """Add a concept to track and retroactively map it to past interactions."""
    normalized = normalize_concept(request.concept_name)
    if not normalized:
        raise HTTPException(status_code=400, detail="Invalid concept name")

    # Check for duplicates
    existing = await db.execute(
        select(func.count(ConceptMastery.id)).where(
            ConceptMastery.course_id == course_id,
            ConceptMastery.concept_name == normalized,
        )
    )
    if (existing.scalar() or 0) > 0:
        raise HTTPException(status_code=409, detail="Concept already tracked")

    # Find matching MemoryRecords: concept in array OR mentioned in content
    result = await db.execute(
        select(MemoryRecord)
        .where(
            MemoryRecord.course_id == course_id,
            MemoryRecord.is_compressed.is_(False),
            or_(
                MemoryRecord.concepts.any(normalized),
                func.lower(MemoryRecord.content).contains(normalized),
            ),
        )
        .order_by(MemoryRecord.created_at.asc())
    )
    matching_records = result.scalars().all()

    # Group by student, replay BKT chronologically
    student_records: dict[uuid.UUID, list] = defaultdict(list)
    for rec in matching_records:
        student_records[rec.student_id].append(rec)

    params = BKTParams()
    now = datetime.now(timezone.utc)
    students_affected = 0

    for student_id, records in student_records.items():
        p_learned = params.p_l0
        times_practiced = 0
        times_struggled = 0
        obs_history: list[dict] = []
        last_practiced = None

        for rec in records:
            score = rec.confusion_score if rec.confusion_score is not None else 0.5
            correct = confusion_to_correct(score)
            p_learned = bkt_update(p_learned, correct, params)
            times_practiced += 1
            if not correct:
                times_struggled += 1
            obs_history.append({
                "correct": correct,
                "confusion": score,
                "timestamp": rec.created_at.isoformat() if rec.created_at else now.isoformat(),
            })
            last_practiced = rec.created_at

        db.add(ConceptMastery(
            student_id=student_id,
            course_id=course_id,
            concept_name=normalized,
            mastery_level=p_learned,
            times_practiced=times_practiced,
            times_struggled=times_struggled,
            last_practiced_at=last_practiced or now,
            evidence={
                "bkt_p_learned": p_learned,
                "bkt_params": {
                    "p_l0": params.p_l0,
                    "p_transit": params.p_transit,
                    "p_guess": params.p_guess,
                    "p_slip": params.p_slip,
                },
                "observation_history": obs_history[-20:],
                "retroactive": True,
            },
        ))
        students_affected += 1

    await db.commit()

    # Build the heatmap cell
    if students_affected > 0:
        agg = await db.execute(
            select(
                func.avg(ConceptMastery.mastery_level).label("avg_mastery"),
                func.sum(ConceptMastery.times_struggled).label("total_struggled"),
                func.count(ConceptMastery.student_id.distinct()).label("student_count"),
            ).where(
                ConceptMastery.course_id == course_id,
                ConceptMastery.concept_name == normalized,
            )
        )
        row = agg.one()
        avg_mastery = float(row.avg_mastery)
        cell = {
            "concept": normalized,
            "mastery_label": _mastery_label(avg_mastery),
            "mastery_value": round(avg_mastery, 2),
            "student_count": int(row.student_count),
            "times_struggled": int(row.total_struggled),
        }
    else:
        cell = {
            "concept": normalized,
            "mastery_label": "no data yet",
            "mastery_value": 0.0,
            "student_count": 0,
            "times_struggled": 0,
        }

    return AddConceptResponse(
        cell=cell,
        students_affected=students_affected,
        memories_matched=len(matching_records),
    )


# ── Strategy Evolution ──


class StrategyInfo(BaseModel):
    id: str
    name: str
    strategy_type: str
    generation: int
    is_active: bool
    is_baseline: bool
    total_uses: int
    avg_score: float | None
    success_rate: float | None
    parent_strategy_id: str | None
    created_at: str


class EvolutionStatusResponse(BaseModel):
    total_strategies: int
    active_count: int
    strategies: list[StrategyInfo]


@router.get("/evolution/status", response_model=EvolutionStatusResponse)
async def get_evolution_status(
    _user_id: uuid.UUID = Depends(require_instructor),
    db: AsyncSession = Depends(get_db),
) -> EvolutionStatusResponse:
    """Return all strategies with scores, uses, generation, and lineage."""
    result = await db.execute(
        select(Strategy).order_by(Strategy.generation.asc(), Strategy.created_at.desc())
    )
    strategies = result.scalars().all()

    items = [
        StrategyInfo(
            id=str(s.id),
            name=s.name,
            strategy_type=s.strategy_type,
            generation=s.generation or 0,
            is_active=s.is_active,
            is_baseline=s.is_baseline,
            total_uses=s.total_uses or 0,
            avg_score=round(s.avg_score, 3) if s.avg_score is not None else None,
            success_rate=round(s.success_rate, 3) if s.success_rate is not None else None,
            parent_strategy_id=str(s.parent_strategy_id) if s.parent_strategy_id else None,
            created_at=s.created_at.isoformat() if s.created_at else "",
        )
        for s in strategies
    ]

    return EvolutionStatusResponse(
        total_strategies=len(items),
        active_count=sum(1 for s in items if s.is_active),
        strategies=items,
    )


class EvolutionTriggerResponse(BaseModel):
    mutations: int
    mutated_from: list[str]
    pruned: int
    pruned_names: list[str]
    active_count: int


@router.post("/evolution/trigger", response_model=EvolutionTriggerResponse)
async def trigger_evolution(
    _user_id: uuid.UUID = Depends(require_instructor),
    db: AsyncSession = Depends(get_db),
    claude: ClaudeClient = Depends(get_claude),
) -> EvolutionTriggerResponse:
    """Manually trigger one strategy evolution cycle."""
    from docere.core.improvement.strategy_evolver import StrategyEvolver

    evolver = StrategyEvolver(db, claude)
    summary = await evolver.evolve()
    await db.commit()

    return EvolutionTriggerResponse(
        mutations=summary.get("mutations", 0),
        mutated_from=summary.get("mutated_from", []),
        pruned=summary.get("pruned", 0),
        pruned_names=summary.get("pruned_names", []),
        active_count=summary.get("active_count", 0),
    )
