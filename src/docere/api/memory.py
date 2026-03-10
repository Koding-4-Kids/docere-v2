"""Memory visualization endpoints (student view)."""

import uuid

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
            last_practiced_at=(
                c.last_practiced_at.isoformat()
                if c.last_practiced_at
                else None
            ),
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
        total_interactions=(
            profile.total_interactions if profile else 0
        ),
        total_messages=profile.total_messages if profile else 0,
        avg_confusion=(
            round(profile.avg_confusion_score, 2) if profile else 0.0
        ),
        engagement_level=(
            profile.engagement_level if profile else "unknown"
        ),
        current_grade=profile.current_grade if profile else None,
        memory_count=mem_count,
        concept_count=concept_count,
        avg_interaction_score=(
            round(profile.avg_interaction_score, 2) if profile else 0.0
        ),
    )
