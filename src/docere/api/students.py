"""Student profile endpoints (instructor view)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from docere.dependencies import get_db, require_instructor
from docere.models.conversation import Conversation, Message
from docere.models.course import Enrollment
from docere.models.memory import ConceptMastery, MemoryRecord, StudentProfile
from docere.models.verification import InteractionScore

router = APIRouter()


class StudentListItem(BaseModel):
    student_id: str
    name: str
    engagement_level: str
    avg_confusion: float
    current_grade: float | None = None
    total_interactions: int = 0
    last_interaction_at: str | None = None


@router.get(
    "/courses/{course_id}/students",
    response_model=list[StudentListItem],
)
async def list_students(
    course_id: uuid.UUID,
    _user_id: uuid.UUID = Depends(require_instructor),
    db: AsyncSession = Depends(get_db),
) -> list[StudentListItem]:
    """List enrolled students with profile summaries."""
    from docere.models.user import User

    result = await db.execute(
        select(User.id, User.name, StudentProfile)
        .join(Enrollment, Enrollment.user_id == User.id)
        .outerjoin(
            StudentProfile,
            (StudentProfile.student_id == User.id) & (StudentProfile.course_id == course_id),
        )
        .where(
            Enrollment.course_id == course_id,
            Enrollment.lms_role == "student",
        )
        .order_by(User.name)
    )

    return [
        StudentListItem(
            student_id=str(uid),
            name=uname or "Unknown",
            engagement_level=(profile.engagement_level if profile else "unknown"),
            avg_confusion=(round(profile.avg_confusion_score, 2) if profile else 0.0),
            current_grade=profile.current_grade if profile else None,
            total_interactions=(profile.total_interactions if profile else 0),
            last_interaction_at=(
                profile.last_interaction_at.isoformat()
                if profile and profile.last_interaction_at
                else None
            ),
        )
        for uid, uname, profile in result.all()
    ]


class ConceptItem(BaseModel):
    concept: str
    mastery_level: float
    times_practiced: int
    times_struggled: int


class StudentProfileResponse(BaseModel):
    student_id: str
    name: str
    engagement_level: str
    avg_confusion: float
    avg_interaction_score: float
    current_grade: float | None = None
    total_interactions: int = 0
    total_messages: int = 0
    last_interaction_at: str | None = None
    profile_summary: str | None = None
    top_concepts: list[ConceptItem] = []
    memory_counts: dict[str, int] = {}


@router.get(
    "/courses/{course_id}/students/{student_id}/profile",
    response_model=StudentProfileResponse,
)
async def get_student_profile(
    course_id: uuid.UUID,
    student_id: uuid.UUID,
    _user_id: uuid.UUID = Depends(require_instructor),
    db: AsyncSession = Depends(get_db),
) -> StudentProfileResponse:
    """Get detailed student profile with memory summary."""
    from docere.models.user import User

    user = await db.get(User, student_id)
    if not user:
        raise HTTPException(status_code=404, detail="Student not found")

    # Profile
    prof_result = await db.execute(
        select(StudentProfile).where(
            StudentProfile.student_id == student_id,
            StudentProfile.course_id == course_id,
        )
    )
    profile = prof_result.scalar_one_or_none()

    # Top concepts
    concept_result = await db.execute(
        select(ConceptMastery)
        .where(
            ConceptMastery.student_id == student_id,
            ConceptMastery.course_id == course_id,
        )
        .order_by(ConceptMastery.times_struggled.desc())
        .limit(15)
    )
    concepts = [
        ConceptItem(
            concept=c.concept_name,
            mastery_level=round(c.mastery_level, 2),
            times_practiced=c.times_practiced,
            times_struggled=c.times_struggled,
        )
        for c in concept_result.scalars().all()
    ]

    # Memory counts by type
    mem_result = await db.execute(
        select(
            MemoryRecord.memory_type,
            func.count(MemoryRecord.id),
        )
        .where(
            MemoryRecord.student_id == student_id,
            MemoryRecord.course_id == course_id,
            MemoryRecord.is_compressed.is_(False),
        )
        .group_by(MemoryRecord.memory_type)
    )
    mem_counts = {r[0]: r[1] for r in mem_result.all()}

    return StudentProfileResponse(
        student_id=str(student_id),
        name=user.name or "Unknown",
        engagement_level=(profile.engagement_level if profile else "unknown"),
        avg_confusion=(round(profile.avg_confusion_score, 2) if profile else 0.0),
        avg_interaction_score=(round(profile.avg_interaction_score, 2) if profile else 0.0),
        current_grade=profile.current_grade if profile else None,
        total_interactions=(profile.total_interactions if profile else 0),
        total_messages=profile.total_messages if profile else 0,
        last_interaction_at=(
            profile.last_interaction_at.isoformat()
            if profile and profile.last_interaction_at
            else None
        ),
        profile_summary=profile.profile_summary if profile else None,
        top_concepts=concepts,
        memory_counts=mem_counts,
    )


class MemoryItem(BaseModel):
    id: str
    memory_type: str
    content: str
    concepts: list[str] | None = None
    sentiment: str | None = None
    confusion_score: float = 0.0
    created_at: str


@router.get(
    "/courses/{course_id}/students/{student_id}/memories",
    response_model=list[MemoryItem],
)
async def get_student_memories(
    course_id: uuid.UUID,
    student_id: uuid.UUID,
    memory_type: str | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    _user_id: uuid.UUID = Depends(require_instructor),
    db: AsyncSession = Depends(get_db),
) -> list[MemoryItem]:
    """View student's memory tree (struggles, breakthroughs, patterns)."""
    query = select(MemoryRecord).where(
        MemoryRecord.student_id == student_id,
        MemoryRecord.course_id == course_id,
        MemoryRecord.is_compressed.is_(False),
    )
    if memory_type:
        query = query.where(MemoryRecord.memory_type == memory_type)

    query = query.order_by(MemoryRecord.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(query)

    return [
        MemoryItem(
            id=str(m.id),
            memory_type=m.memory_type,
            content=m.content,
            concepts=m.concepts,
            sentiment=m.sentiment,
            confusion_score=m.confusion_score or 0.0,
            created_at=m.created_at.isoformat(),
        )
        for m in result.scalars().all()
    ]


class InteractionItem(BaseModel):
    conversation_id: str
    conversation_title: str | None = None
    message_id: str
    assistant_content: str
    student_content: str | None = None
    created_at: str
    # Scores
    helpfulness: float | None = None
    clarity: float | None = None
    engagement: float | None = None
    understanding_delta: float | None = None
    composite_score: float | None = None


@router.get(
    "/courses/{course_id}/students/{student_id}/interactions",
    response_model=list[InteractionItem],
)
async def get_student_interactions(
    course_id: uuid.UUID,
    student_id: uuid.UUID,
    limit: int = Query(default=30, le=100),
    offset: int = 0,
    _user_id: uuid.UUID = Depends(require_instructor),
    db: AsyncSession = Depends(get_db),
) -> list[InteractionItem]:
    """View interaction history with process verification scores."""
    # Get scored interactions for this student
    result = await db.execute(
        select(InteractionScore, Message, Conversation)
        .join(Message, InteractionScore.message_id == Message.id)
        .join(
            Conversation,
            InteractionScore.conversation_id == Conversation.id,
        )
        .where(
            InteractionScore.student_id == student_id,
            Conversation.course_id == course_id,
        )
        .order_by(InteractionScore.scored_at.desc())
        .offset(offset)
        .limit(limit)
    )

    items: list[InteractionItem] = []
    for score, msg, conv in result.all():
        # Find the preceding student message
        student_msg_result = await db.execute(
            select(Message.content)
            .where(
                Message.conversation_id == conv.id,
                Message.role == "user",
                Message.created_at <= msg.created_at,
            )
            .order_by(Message.created_at.desc())
            .limit(1)
        )
        student_content = student_msg_result.scalar_one_or_none()

        items.append(
            InteractionItem(
                conversation_id=str(conv.id),
                conversation_title=conv.title,
                message_id=str(msg.id),
                assistant_content=msg.content[:500],
                student_content=(student_content[:500] if student_content else None),
                created_at=msg.created_at.isoformat(),
                helpfulness=score.helpfulness_score,
                clarity=score.clarity_score,
                engagement=score.engagement_score,
                understanding_delta=score.understanding_delta,
                composite_score=score.composite_score,
            )
        )
    return items
