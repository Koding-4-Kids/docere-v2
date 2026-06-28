"""Background task: periodic LMS sync (every 2 hours).

After syncing grades, processes changes through:
1. OutcomeTracker: links grades back to tutoring interaction scores
2. MemoryLayer: creates memory records so the agent knows about grades

After syncing materials, embeds new/updated content into Qdrant.
"""
# E501 intentional here: file holds long prompt/instruction string constants.
# ruff: noqa: E501

import re
import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from docere.core.improvement.strategy_archive import StrategyArchive
from docere.core.memory.concept_utils import normalize_concept
from docere.core.memory.memory_layer import MemoryLayer
from docere.core.memory.teacher_context import TeacherContextManager
from docere.core.verification.outcome_tracker import OutcomeTracker
from docere.integrations.llm.client import ClaudeClient
from docere.integrations.lms.canvas import CanvasAdapter
from docere.integrations.lms.moodle import MoodleAdapter
from docere.integrations.vector_db.qdrant import QdrantStore
from docere.models.course import Assignment, Course, CourseMaterial
from docere.services.lms_sync_service import GradeChange, LMSSyncService

logger = structlog.get_logger()


async def sync_all_courses(
    db: AsyncSession,
    claude: ClaudeClient | None = None,
    qdrant: QdrantStore | None = None,
) -> dict[str, int]:
    """Sync all LMS-enabled courses. Run every 2 hours via ARQ.

    After syncing, processes grade changes through:
    - OutcomeTracker: backfills subsequent_performance on interaction scores
    - MemoryLayer: creates grade memory records for the agent

    Also embeds any new/updated materials into Qdrant.
    """
    result = await db.execute(select(Course).where(Course.lms_sync_enabled.is_(True)))
    courses = result.scalars().all()

    synced = 0
    errors = 0
    all_grade_changes: list[GradeChange] = []
    materials_embedded = 0

    for course in courses:
        try:
            if course.lms_platform == "canvas":
                adapter: CanvasAdapter | MoodleAdapter = CanvasAdapter()
            elif course.lms_platform == "moodle":
                adapter = MoodleAdapter()
            else:
                logger.warning("Unknown LMS platform", platform=course.lms_platform)
                continue

            service = LMSSyncService(db, adapter)
            summary, grade_changes = await service.incremental_sync(course.id)
            all_grade_changes.extend(grade_changes)
            synced += 1
            logger.info(
                "Synced course",
                course_id=str(course.id),
                name=course.name,
                grade_changes=len(grade_changes),
            )

            # Embed new/updated materials
            if claude and qdrant:
                embedded = await _embed_new_materials(db, course, qdrant, claude)
                materials_embedded += embedded
        except Exception:
            errors += 1
            logger.exception("Failed to sync course", course_id=str(course.id))

    # Process grade changes through outcome tracker and memory layer
    outcomes_linked = 0
    if all_grade_changes:
        outcomes_linked = await _process_grade_changes(db, all_grade_changes, claude, qdrant)

    return {
        "synced": synced,
        "errors": errors,
        "grade_changes": len(all_grade_changes),
        "outcomes_linked": outcomes_linked,
        "materials_embedded": materials_embedded,
    }


async def _embed_new_materials(
    db: AsyncSession,
    course: Course,
    qdrant: QdrantStore,
    claude: ClaudeClient,
) -> int:
    """Embed materials that have no embedding_id (new or updated).

    For materials with cleared embedding_id (content changed), calls
    refresh_course to delete old vectors and re-embed.
    """
    ctx_manager = TeacherContextManager(qdrant, claude)
    course_id_str = str(course.id)

    # Find materials needing embedding
    result = await db.execute(
        select(CourseMaterial).where(
            CourseMaterial.course_id == course.id,
            CourseMaterial.embedding_id.is_(None),
            CourseMaterial.content.isnot(None),
        )
    )
    unembedded = result.scalars().all()

    if not unembedded:
        return 0

    # Separate truly new (no content_hash change history) vs updated
    # For simplicity, treat all as needing fresh embedding via refresh_course
    materials_data = [
        {
            "title": m.title or "",
            "content": m.content or "",
            "type": m.material_type,
        }
        for m in unembedded
        if m.content and len(m.content.strip()) >= 50
    ]

    if not materials_data:
        return 0

    chunks = await ctx_manager.refresh_course(course_id_str, materials_data)

    # Mark materials as embedded
    for material in unembedded:
        if material.content and len(material.content.strip()) >= 50:
            material.embedding_id = f"materials_{course_id_str}"
    await db.flush()

    logger.info(
        "Embedded new/updated materials",
        course_id=course_id_str,
        materials=len(materials_data),
        chunks=chunks,
    )
    return chunks


_STOP_WORDS = {
    "a",
    "an",
    "the",
    "and",
    "or",
    "of",
    "for",
    "in",
    "on",
    "to",
    "is",
    "it",
    "at",
    "by",
    "with",
    "from",
    "as",
    "this",
    "that",
    "be",
    "are",
    "was",
    "were",
    "been",
    "has",
    "have",
    "had",
    "do",
    "does",
    "did",
    "will",
    "would",
    "could",
    "should",
    "may",
    "might",
    "can",
    "shall",
    "not",
    "no",
    "but",
    "if",
    "so",
    "than",
    "then",
    "each",
    "every",
    "all",
    "any",
    "few",
    "more",
    "most",
    "other",
    "some",
    "such",
    "only",
    "own",
    "same",
    "too",
    "very",
    "just",
    "about",
    "above",
    "after",
    "before",
    "between",
    "into",
    "through",
    "during",
    "up",
    "down",
    "out",
    "off",
    "over",
    "under",
    "assignment",
    "quiz",
    "exam",
    "test",
    "homework",
    "hw",
    "lab",
    "project",
    "problem",
    "set",
    "part",
    "section",
    "chapter",
    "unit",
    "week",
    "module",
    "final",
    "midterm",
    "review",
    "practice",
    "graded",
    "extra",
    "credit",
}

# Cache to avoid repeated LLM calls for the same assignment
_concept_cache: dict[str, list[str]] = {}

CONCEPT_EXTRACT_PROMPT = """Extract 3-5 academic topic keywords from this assignment. Return ONLY a JSON array of lowercase strings.

Title: {title}
Description: {description}

Example: ["derivatives", "chain rule", "implicit differentiation"]"""


async def _extract_assignment_concepts(
    assignment_id: str,
    title: str,
    description: str | None,
    claude: ClaudeClient | None,
) -> list[str]:
    """Extract topic concepts from an assignment's title and description.

    Uses Claude if available and the assignment has a description.
    Falls back to splitting the title into meaningful words.
    Results are cached per assignment_id.
    """
    if assignment_id in _concept_cache:
        return _concept_cache[assignment_id]

    concepts: list[str] = []

    # Try Claude extraction if we have a description
    if claude and description and len(description.strip()) > 20:
        try:
            import json

            result = await claude.chat(
                system_prompt="Extract academic topics. Respond with only a JSON array.",
                messages=[
                    {
                        "role": "user",
                        "content": CONCEPT_EXTRACT_PROMPT.format(
                            title=title,
                            description=description[:500],
                        ),
                    }
                ],
                max_tokens=100,
                temperature=0.1,
            )
            json_start = result.find("[")
            json_end = result.rfind("]") + 1
            if json_start >= 0 and json_end > json_start:
                concepts = json.loads(result[json_start:json_end])
                concepts = [normalize_concept(c) for c in concepts if isinstance(c, str)]
        except Exception:
            logger.debug("Claude concept extraction failed, falling back to title", title=title)

    # Fallback: extract meaningful words from the title
    if not concepts:
        words = re.split(r"[\s\-_:,/]+", title.lower())
        concepts = [w for w in words if len(w) > 2 and w not in _STOP_WORDS and not w.isdigit()]

    # Always include the full title for broader matching
    concepts.append(normalize_concept(title))

    _concept_cache[assignment_id] = concepts
    return concepts


async def _process_grade_changes(
    db: AsyncSession,
    changes: list[GradeChange],
    claude: ClaudeClient | None,
    qdrant: QdrantStore | None,
) -> int:
    """Process grade changes: link to interaction scores and create memory records."""
    strategy_archive = StrategyArchive(db)
    tracker = OutcomeTracker(db, strategy_archive=strategy_archive)
    total_linked = 0

    # Pre-fetch assignment descriptions for concept extraction
    assignment_ids = list({change.assignment_id for change in changes})
    assignment_descs: dict[uuid.UUID, str | None] = {}
    if assignment_ids:
        result = await db.execute(
            select(Assignment.id, Assignment.description).where(Assignment.id.in_(assignment_ids))
        )
        for aid, desc in result.all():
            assignment_descs[aid] = desc

    for change in changes:
        # Extract real topic concepts from assignment
        concepts = await _extract_assignment_concepts(
            assignment_id=str(change.assignment_id),
            title=change.assignment_title,
            description=assignment_descs.get(change.assignment_id),
            claude=claude,
        )

        # 1. Link grade to recent tutoring interactions (backfill subsequent_performance)
        try:
            linked, _ids = await tracker.link_grade_to_interactions(
                student_id=str(change.student_id),
                course_id=str(change.course_id),
                assignment_id=str(change.assignment_id),
                score=change.score,
                max_score=change.max_score,
                concepts=concepts,
            )
            total_linked += linked
        except Exception:
            logger.exception(
                "Failed to link grade to interactions",
                student_id=str(change.student_id),
            )

        # 2. Create memory record so agent knows about the grade
        if claude and qdrant:
            try:
                memory = MemoryLayer(db, qdrant, claude)
                await memory.integrate_grade(
                    student_id=str(change.student_id),
                    course_id=str(change.course_id),
                    assignment_title=change.assignment_title,
                    score=change.score,
                    max_score=change.max_score,
                    concepts=concepts,
                )
            except Exception:
                logger.exception(
                    "Failed to integrate grade into memory",
                    student_id=str(change.student_id),
                )

    await db.flush()

    logger.info(
        "Grade changes processed",
        total_changes=len(changes),
        interactions_linked=total_linked,
    )
    return total_linked
