"""Memory visualization endpoints (student view)."""

import uuid
from collections import defaultdict

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from docere.dependencies import get_current_user_id, get_db
from docere.models.memory import ConceptMastery, MemoryRecord, StudentProfile

router = APIRouter()


class MemorySummaryItem(BaseModel):
    id: str
    memory_type: str
    content: str
    concepts: list[str] | None = None
    sentiment: str | None = None
    confusion_score: float = 0.0
    created_at: str


class MyMemoryResponse(BaseModel):
    total_memories: int = 0
    by_type: dict[str, list[MemorySummaryItem]] = {}


@router.get("/me/{course_id}", response_model=MyMemoryResponse)
async def get_my_memory(
    course_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> MyMemoryResponse:
    """Get student's own memory summary for a course."""
    result = await db.execute(
        select(MemoryRecord)
        .where(
            MemoryRecord.student_id == user_id,
            MemoryRecord.course_id == course_id,
            MemoryRecord.is_compressed.is_(False),
        )
        .order_by(MemoryRecord.created_at.desc())
        .limit(100)
    )
    records = result.scalars().all()

    by_type: dict[str, list[MemorySummaryItem]] = {}
    for r in records:
        item = MemorySummaryItem(
            id=str(r.id),
            memory_type=r.memory_type,
            content=r.content,
            concepts=r.concepts,
            sentiment=r.sentiment,
            confusion_score=r.confusion_score or 0.0,
            created_at=r.created_at.isoformat(),
        )
        by_type.setdefault(r.memory_type, [])
        if len(by_type[r.memory_type]) < 5:
            by_type[r.memory_type].append(item)

    return MyMemoryResponse(total_memories=len(records), by_type=by_type)


class MyConceptItem(BaseModel):
    concept: str
    mastery_level: float
    mastery_label: str
    times_practiced: int
    times_struggled: int
    last_practiced_at: str | None = None


@router.get(
    "/me/{course_id}/concepts",
    response_model=list[MyConceptItem],
)
async def get_my_concepts(
    course_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[MyConceptItem]:
    """Get student's concept mastery overview."""
    result = await db.execute(
        select(ConceptMastery)
        .where(
            ConceptMastery.student_id == user_id,
            ConceptMastery.course_id == course_id,
        )
        .order_by(ConceptMastery.mastery_level.asc())
    )

    def _label(level: float) -> str:
        if level >= 0.8:
            return "mastered"
        if level >= 0.5:
            return "developing"
        return "struggling"

    return [
        MyConceptItem(
            concept=c.concept_name,
            mastery_level=round(c.mastery_level, 2),
            mastery_label=_label(c.mastery_level),
            times_practiced=c.times_practiced,
            times_struggled=c.times_struggled,
            last_practiced_at=(c.last_practiced_at.isoformat() if c.last_practiced_at else None),
        )
        for c in result.scalars().all()
    ]


class MyStatsResponse(BaseModel):
    total_interactions: int = 0
    total_messages: int = 0
    avg_confusion: float = 0.0
    engagement_level: str = "unknown"
    current_grade: float | None = None
    memory_count: int = 0
    concept_count: int = 0
    avg_interaction_score: float = 0.0


@router.get(
    "/me/{course_id}/stats",
    response_model=MyStatsResponse,
)
async def get_my_stats(
    course_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> MyStatsResponse:
    """Get memory statistics (total interactions, memory count, etc)."""
    # Profile
    prof_result = await db.execute(
        select(StudentProfile).where(
            StudentProfile.student_id == user_id,
            StudentProfile.course_id == course_id,
        )
    )
    profile = prof_result.scalar_one_or_none()

    # Memory count
    mem_count_result = await db.execute(
        select(func.count(MemoryRecord.id)).where(
            MemoryRecord.student_id == user_id,
            MemoryRecord.course_id == course_id,
            MemoryRecord.is_compressed.is_(False),
        )
    )
    mem_count = mem_count_result.scalar() or 0

    # Concept count
    concept_count_result = await db.execute(
        select(func.count(ConceptMastery.id)).where(
            ConceptMastery.student_id == user_id,
            ConceptMastery.course_id == course_id,
        )
    )
    concept_count = concept_count_result.scalar() or 0

    return MyStatsResponse(
        total_interactions=(profile.total_interactions if profile else 0),
        total_messages=profile.total_messages if profile else 0,
        avg_confusion=(round(profile.avg_confusion_score, 2) if profile else 0.0),
        engagement_level=(profile.engagement_level if profile else "unknown"),
        current_grade=profile.current_grade if profile else None,
        memory_count=mem_count,
        concept_count=concept_count,
        avg_interaction_score=(round(profile.avg_interaction_score, 2) if profile else 0.0),
    )


# ── Memory Graph (student's own network) ──


class MemoryGraphNode(BaseModel):
    id: str
    name: str
    type: str  # "memory", "concept", "document"
    # Memory fields
    memory_type: str | None = None
    content: str | None = None
    concepts: list[str] | None = None
    confusion_score: float | None = None
    sentiment: str | None = None
    # Concept fields
    mastery_level: float | None = None
    mastery_label: str | None = None
    times_practiced: int | None = None
    times_struggled: int | None = None
    # Document fields
    doc_type: str | None = None  # "textbook", "slides", "notes", "rubric", "docs", "image", "other"
    filename: str | None = None
    status: str | None = None  # "uploaded", "processing", "completed", "failed"
    page_count: int | None = None
    chunk_count: int | None = None


class MemoryGraphEdge(BaseModel):
    source: str
    target: str
    type: str  # "memory_concept", "doc_concept", "concept_concept", "memory_memory"
    weight: float | None = None


class MemoryGraphResponse(BaseModel):
    nodes: list[MemoryGraphNode]
    edges: list[MemoryGraphEdge]


def _looks_like_slides(text: str, page_count: int | None) -> bool:
    """Heuristic: detect slide decks from extracted text content."""
    if not text:
        return False

    lines = text.strip().splitlines()
    if not lines:
        return False

    # Slide decks exported to PDF have many short pages
    # If we have page count and text, check avg text per page
    if page_count and page_count >= 5:
        avg_chars_per_page = len(text) / page_count
        # Slides: ~100-500 chars/page. Textbooks: 2000+
        if avg_chars_per_page < 600:
            return True

    # Count bullet-like lines (start with -, *, •, >, or numbered)
    bullet_count = 0
    short_line_count = 0
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if len(stripped) < 80:
            short_line_count += 1
        if stripped[:1] in ("-", "*", ">") or stripped.startswith("•"):
            bullet_count += 1
        # Numbered bullets: "1.", "1)", etc.
        if len(stripped) > 1 and stripped[0].isdigit() and stripped[1] in (".", ")"):
            bullet_count += 1

    non_empty = sum(1 for l in lines if l.strip())
    if non_empty == 0:
        return False

    bullet_ratio = bullet_count / non_empty
    short_ratio = short_line_count / non_empty

    # Slide decks are mostly short lines and bullets
    if short_ratio > 0.7 and bullet_ratio > 0.15:
        return True
    if short_ratio > 0.8:
        return True

    # Check for slide markers in text
    text_lower = text[:2000].lower()
    slide_markers = (
        "slide ",
        "slide\n",
        "agenda",
        "outline\n",
        "key takeaway",
        "learning objective",
    )
    if sum(1 for m in slide_markers if m in text_lower) >= 2:
        return True

    return False


def _classify_document(
    filename: str,
    mime_type: str | None = None,
    extracted_text: str | None = None,
    page_count: int | None = None,
) -> str:
    """Classify a document type from filename, mime type, and content analysis."""
    name = filename.lower()

    # Slides (native formats)
    if any(name.endswith(ext) for ext in (".pptx", ".ppt", ".key")):
        return "slides"
    if "slide" in name or "presentation" in name or "lecture" in name:
        return "slides"

    # Notes
    if any(name.endswith(ext) for ext in (".md", ".txt")):
        return "notes"
    if "note" in name or "summary" in name or "review" in name:
        return "notes"

    # Rubric
    if "rubric" in name or "grading" in name or "criteria" in name:
        return "rubric"

    # Images
    if any(name.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".gif", ".webp")):
        return "image"

    # Spreadsheets
    if any(name.endswith(ext) for ext in (".xlsx", ".xls", ".csv")):
        return "spreadsheet"

    # PDF — use content analysis to distinguish slides from textbooks
    if name.endswith(".pdf"):
        if "syllabus" in name:
            return "syllabus"
        if "hw" in name or "homework" in name or "assignment" in name or "problem" in name:
            return "assignment"
        if (
            "exam" in name
            or "quiz" in name
            or "test" in name
            or "midterm" in name
            or "final" in name
        ):
            return "exam"
        if "slide" in name or "deck" in name or "ppt" in name:
            return "slides"
        if "textbook" in name or "chapter" in name:
            return "textbook"
        # Content-based detection for ambiguous PDFs
        if extracted_text and _looks_like_slides(extracted_text, page_count):
            return "slides"
        # Default: if short page count, likely slides; if long, textbook
        if page_count and page_count >= 5 and page_count <= 200:
            # Still ambiguous — lean on text analysis or default
            pass
        return "textbook"

    # DOCX
    if any(name.endswith(ext) for ext in (".docx", ".doc")):
        if "essay" in name or "report" in name or "paper" in name:
            return "docs"
        return "notes"

    # HTML
    if any(name.endswith(ext) for ext in (".html", ".htm")):
        return "docs"

    return "other"


def _mastery_label(level: float) -> str:
    if level >= 0.8:
        return "mastered"
    if level >= 0.5:
        return "developing"
    return "struggling"


@router.get(
    "/me/{course_id}/graph",
    response_model=MemoryGraphResponse,
)
async def get_my_memory_graph(
    course_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> MemoryGraphResponse:
    """Build student's personal memory graph: memories + concepts + documents."""
    from docere.models.document import StudentDocument

    nodes: list[MemoryGraphNode] = []
    edges: list[MemoryGraphEdge] = []

    # Track concept → node IDs for cross-edges
    concept_to_nodes: dict[str, list[str]] = defaultdict(list)

    # ── 1. Memories (from conversations) ──
    mem_result = await db.execute(
        select(MemoryRecord)
        .where(
            MemoryRecord.student_id == user_id,
            MemoryRecord.course_id == course_id,
            MemoryRecord.is_compressed.is_(False),
        )
        .order_by(MemoryRecord.created_at.desc())
        .limit(80)
    )
    memories = mem_result.scalars().all()

    for mem in memories:
        mid = f"mem_{mem.id}"
        short_content = (mem.content[:120] + "...") if len(mem.content) > 120 else mem.content
        nodes.append(
            MemoryGraphNode(
                id=mid,
                name=short_content,
                type="memory",
                memory_type=mem.memory_type,
                content=short_content,
                concepts=mem.concepts,
                confusion_score=round(mem.confusion_score, 2) if mem.confusion_score else 0.0,
                sentiment=mem.sentiment,
            )
        )
        if mem.concepts:
            for concept in mem.concepts:
                concept_to_nodes[concept.lower()].append(mid)

    # ── 2. Concepts (mastery tracking) ──
    concept_result = await db.execute(
        select(ConceptMastery)
        .where(
            ConceptMastery.student_id == user_id,
            ConceptMastery.course_id == course_id,
        )
        .order_by(ConceptMastery.mastery_level.asc())
    )
    concepts = concept_result.scalars().all()

    concept_node_ids: dict[str, str] = {}
    for c in concepts:
        cid = f"concept_{c.concept_name}"
        concept_node_ids[c.concept_name.lower()] = cid
        nodes.append(
            MemoryGraphNode(
                id=cid,
                name=c.concept_name,
                type="concept",
                mastery_level=round(c.mastery_level, 2),
                mastery_label=_mastery_label(c.mastery_level),
                times_practiced=c.times_practiced,
                times_struggled=c.times_struggled,
            )
        )

    # ── 3. Documents ──
    doc_result = await db.execute(
        select(StudentDocument)
        .where(
            StudentDocument.student_id == user_id,
            StudentDocument.course_id == course_id,
        )
        .order_by(StudentDocument.created_at.desc())
    )
    documents = doc_result.scalars().all()

    for doc in documents:
        did = f"doc_{doc.id}"
        doc_type = _classify_document(
            doc.filename,
            doc.mime_type,
            extracted_text=doc.extracted_text,
            page_count=doc.page_count,
        )
        nodes.append(
            MemoryGraphNode(
                id=did,
                name=doc.filename,
                type="document",
                doc_type=doc_type,
                filename=doc.filename,
                status=doc.status,
                page_count=doc.page_count,
                chunk_count=doc.chunk_count,
            )
        )

    # ── 4. Build edges ──

    # Memory → Concept edges
    for mem in memories:
        mid = f"mem_{mem.id}"
        if mem.concepts:
            for concept in mem.concepts:
                cid = concept_node_ids.get(concept.lower())
                if cid:
                    edges.append(
                        MemoryGraphEdge(
                            source=mid,
                            target=cid,
                            type="memory_concept",
                        )
                    )

    # Memory ↔ Memory edges (shared concepts)
    for concept_key, mem_ids in concept_to_nodes.items():
        if len(mem_ids) < 2:
            continue
        for i in range(min(len(mem_ids), 4)):
            for j in range(i + 1, min(len(mem_ids), 4)):
                edges.append(
                    MemoryGraphEdge(
                        source=mem_ids[i],
                        target=mem_ids[j],
                        type="memory_memory",
                    )
                )

    # Concept ↔ Concept edges (concepts that share memories)
    concept_keys = list(concept_node_ids.keys())
    concept_shared: dict[str, set[str]] = defaultdict(set)
    for mem in memories:
        if mem.concepts:
            for c in mem.concepts:
                concept_shared[c.lower()].add(f"mem_{mem.id}")

    for i in range(len(concept_keys)):
        for j in range(i + 1, len(concept_keys)):
            shared = concept_shared.get(concept_keys[i], set()) & concept_shared.get(
                concept_keys[j], set()
            )
            if shared:
                edges.append(
                    MemoryGraphEdge(
                        source=concept_node_ids[concept_keys[i]],
                        target=concept_node_ids[concept_keys[j]],
                        type="concept_concept",
                        weight=len(shared)
                        / max(
                            len(concept_shared.get(concept_keys[i], set())),
                            len(concept_shared.get(concept_keys[j], set())),
                            1,
                        ),
                    )
                )

    # Document → Concept edges (simple: match concept names in filename or extracted text preview)
    for doc in documents:
        did = f"doc_{doc.id}"
        doc_text = (
            doc.filename + " " + (doc.extracted_text[:500] if doc.extracted_text else "")
        ).lower()
        for concept_key, cid in concept_node_ids.items():
            if concept_key in doc_text:
                edges.append(
                    MemoryGraphEdge(
                        source=did,
                        target=cid,
                        type="doc_concept",
                    )
                )

    return MemoryGraphResponse(nodes=nodes, edges=edges)
