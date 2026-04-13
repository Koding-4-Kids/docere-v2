"""Analytics and research endpoints."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from docere.dependencies import get_db, require_instructor
from docere.models.course import Enrollment
from docere.models.memory import StudentProfile
from docere.models.strategy import Strategy

router = APIRouter()


class CourseMetricsResponse(BaseModel):
    course_id: str
    student_count: int = 0
    engagement_breakdown: dict[str, int] = {}
    avg_confusion: float = 0.0
    avg_grade: float | None = None
    total_interactions: int = 0
    total_messages: int = 0
    avg_interaction_score: float = 0.0


@router.get(
    "/course/{course_id}/metrics",
    response_model=CourseMetricsResponse,
)
async def get_course_metrics(
    course_id: uuid.UUID,
    _user_id: uuid.UUID = Depends(require_instructor),
    db: AsyncSession = Depends(get_db),
) -> CourseMetricsResponse:
    """Get course-level analytics metrics."""
    # Student count
    count_result = await db.execute(
        select(func.count(Enrollment.id)).where(
            Enrollment.course_id == course_id,
            Enrollment.lms_role == "student",
        )
    )
    student_count = count_result.scalar() or 0

    # Aggregate profile
    agg_result = await db.execute(
        select(
            func.avg(StudentProfile.avg_confusion_score),
            func.avg(StudentProfile.current_grade),
            func.sum(StudentProfile.total_interactions),
            func.sum(StudentProfile.total_messages),
            func.avg(StudentProfile.avg_interaction_score),
        ).where(StudentProfile.course_id == course_id)
    )
    row = agg_result.one()

    # Engagement breakdown
    eng_result = await db.execute(
        select(
            StudentProfile.engagement_level,
            func.count(StudentProfile.id),
        )
        .where(StudentProfile.course_id == course_id)
        .group_by(StudentProfile.engagement_level)
    )
    engagement = {r[0] or "unknown": r[1] for r in eng_result.all()}

    return CourseMetricsResponse(
        course_id=str(course_id),
        student_count=student_count,
        engagement_breakdown=engagement,
        avg_confusion=(round(float(row[0]), 2) if row[0] is not None else 0.0),
        avg_grade=(round(float(row[1]), 1) if row[1] is not None else None),
        total_interactions=int(row[2]) if row[2] is not None else 0,
        total_messages=int(row[3]) if row[3] is not None else 0,
        avg_interaction_score=(round(float(row[4]), 2) if row[4] is not None else 0.0),
    )


class StrategyPerformanceItem(BaseModel):
    id: str
    name: str
    strategy_type: str
    total_uses: int
    avg_score: float | None = None
    success_rate: float | None = None
    is_active: bool
    generation: int


@router.get(
    "/agent/performance",
    response_model=list[StrategyPerformanceItem],
)
async def get_agent_performance(
    _user_id: uuid.UUID = Depends(require_instructor),
    db: AsyncSession = Depends(get_db),
) -> list[StrategyPerformanceItem]:
    """Get agent self-improvement metrics over time."""
    result = await db.execute(
        select(Strategy)
        .where(Strategy.total_uses > 0)
        .order_by(Strategy.avg_score.desc().nullslast())
    )
    return [
        StrategyPerformanceItem(
            id=str(s.id),
            name=s.name,
            strategy_type=s.strategy_type,
            total_uses=s.total_uses or 0,
            avg_score=(round(s.avg_score, 3) if s.avg_score is not None else None),
            success_rate=(round(s.success_rate, 3) if s.success_rate is not None else None),
            is_active=s.is_active,
            generation=s.generation or 0,
        )
        for s in result.scalars().all()
    ]


class StrategyArchiveItem(BaseModel):
    id: str
    name: str
    description: str
    strategy_type: str
    prompt_template: str
    total_uses: int
    avg_score: float | None = None
    success_rate: float | None = None
    is_active: bool
    is_baseline: bool
    generation: int
    parent_strategy_id: str | None = None
    created_at: str


@router.get(
    "/strategies",
    response_model=list[StrategyArchiveItem],
)
async def get_strategy_performance(
    _user_id: uuid.UUID = Depends(require_instructor),
    db: AsyncSession = Depends(get_db),
) -> list[StrategyArchiveItem]:
    """Get strategy archive with performance data."""
    result = await db.execute(
        select(Strategy).order_by(Strategy.generation.asc(), Strategy.created_at.desc())
    )
    return [
        StrategyArchiveItem(
            id=str(s.id),
            name=s.name,
            description=s.description,
            strategy_type=s.strategy_type,
            prompt_template=s.prompt_template,
            total_uses=s.total_uses or 0,
            avg_score=(round(s.avg_score, 3) if s.avg_score is not None else None),
            success_rate=(round(s.success_rate, 3) if s.success_rate is not None else None),
            is_active=s.is_active,
            is_baseline=s.is_baseline,
            generation=s.generation or 0,
            parent_strategy_id=(str(s.parent_strategy_id) if s.parent_strategy_id else None),
            created_at=s.created_at.isoformat() if s.created_at else "",
        )
        for s in result.scalars().all()
    ]


class GroupMetrics(BaseModel):
    group_name: str
    student_count: int = 0
    avg_interaction_score: float = 0.0
    avg_confusion: float = 0.0
    total_interactions: int = 0
    event_count: int = 0


class StudyResultsResponse(BaseModel):
    study_id: str
    study_name: str | None = None
    is_active: bool = False
    groups: dict
    group_metrics: list[GroupMetrics] = []


@router.get(
    "/study/{study_id}/results",
    response_model=StudyResultsResponse,
)
async def get_study_results(
    study_id: uuid.UUID,
    _user_id: uuid.UUID = Depends(require_instructor),
    db: AsyncSession = Depends(get_db),
) -> StudyResultsResponse:
    """Get ablation study results comparing groups."""
    from docere.models.research import ResearchEvent, StudyConfig

    config = await db.get(StudyConfig, study_id)
    if not config:
        raise HTTPException(status_code=404, detail="Study not found")

    # Get per-group events
    event_result = await db.execute(
        select(
            ResearchEvent.event_data["group"].astext.label("group_name"),
            func.count(ResearchEvent.id).label("event_count"),
        )
        .where(ResearchEvent.study_id == study_id)
        .group_by("group_name")
    )
    event_counts = {r.group_name: r.event_count for r in event_result.all()}

    # Build per-group metrics from enrollments
    groups_config = config.groups or {}
    group_metrics: list[GroupMetrics] = []

    for group_name, group_data in groups_config.items():
        student_ids = group_data.get("student_ids", [])
        if not student_ids:
            group_metrics.append(
                GroupMetrics(
                    group_name=group_name,
                    event_count=event_counts.get(group_name, 0),
                )
            )
            continue

        agg = await db.execute(
            select(
                func.count(StudentProfile.id),
                func.avg(StudentProfile.avg_interaction_score),
                func.avg(StudentProfile.avg_confusion_score),
                func.sum(StudentProfile.total_interactions),
            ).where(
                StudentProfile.student_id.in_(student_ids),
                StudentProfile.course_id == config.course_id,
            )
        )
        row = agg.one()
        group_metrics.append(
            GroupMetrics(
                group_name=group_name,
                student_count=int(row[0]) if row[0] else 0,
                avg_interaction_score=(round(float(row[1]), 3) if row[1] is not None else 0.0),
                avg_confusion=(round(float(row[2]), 3) if row[2] is not None else 0.0),
                total_interactions=int(row[3]) if row[3] is not None else 0,
                event_count=event_counts.get(group_name, 0),
            )
        )

    return StudyResultsResponse(
        study_id=str(config.id),
        study_name=config.study_name,
        is_active=config.is_active,
        groups=groups_config,
        group_metrics=group_metrics,
    )


class ConfigureStudyRequest(BaseModel):
    course_id: uuid.UUID
    study_name: str
    groups: dict[str, dict]
    randomization_seed: int | None = None


class ConfigureStudyResponse(BaseModel):
    study_id: str
    student_assignments: dict[str, list[str]] = {}


@router.post(
    "/admin/study/configure",
    response_model=ConfigureStudyResponse,
)
async def configure_study(
    request: ConfigureStudyRequest,
    _user_id: uuid.UUID = Depends(require_instructor),
    db: AsyncSession = Depends(get_db),
) -> ConfigureStudyResponse:
    """Configure ablation study groups for a course."""
    import random

    from docere.models.research import StudyConfig

    # Get enrolled students
    enrollment_result = await db.execute(
        select(Enrollment.user_id).where(
            Enrollment.course_id == request.course_id,
            Enrollment.lms_role == "student",
        )
    )
    student_ids = [str(r[0]) for r in enrollment_result.all()]

    # Randomly assign students to groups
    rng = random.Random(request.randomization_seed)
    rng.shuffle(student_ids)

    group_names = list(request.groups.keys())
    assignments: dict[str, list[str]] = {g: [] for g in group_names}
    for i, sid in enumerate(student_ids):
        group = group_names[i % len(group_names)]
        assignments[group].append(sid)

    # Save group config with assigned student_ids
    groups_with_ids = {}
    for group_name, group_config in request.groups.items():
        groups_with_ids[group_name] = {
            **group_config,
            "student_ids": assignments[group_name],
        }

    config = StudyConfig(
        course_id=request.course_id,
        study_name=request.study_name,
        groups=groups_with_ids,
        randomization_seed=request.randomization_seed,
        started_at=datetime.now(UTC),
    )
    db.add(config)

    # Update enrollments with study_group assignment
    for group_name, sids in assignments.items():
        for sid in sids:
            enrollment_update = await db.execute(
                select(Enrollment).where(
                    Enrollment.user_id == uuid.UUID(sid),
                    Enrollment.course_id == request.course_id,
                )
            )
            enrollment = enrollment_update.scalar_one_or_none()
            if enrollment:
                enrollment.study_group = group_name

    await db.commit()
    await db.refresh(config)

    return ConfigureStudyResponse(
        study_id=str(config.id),
        student_assignments=assignments,
    )


class ExportEvent(BaseModel):
    event_type: str
    group: str | None = None
    event_data: dict
    recorded_at: str


class StudyExportResponse(BaseModel):
    study_id: str
    study_name: str | None = None
    events: list[ExportEvent] = []


@router.get(
    "/admin/study/export",
    response_model=list[StudyExportResponse],
)
async def export_study_data(
    _user_id: uuid.UUID = Depends(require_instructor),
    db: AsyncSession = Depends(get_db),
) -> list[StudyExportResponse]:
    """Export anonymized research data."""
    from docere.models.research import ResearchEvent, StudyConfig

    # Get all studies
    studies = await db.execute(select(StudyConfig).order_by(StudyConfig.created_at.desc()))

    results: list[StudyExportResponse] = []
    for config in studies.scalars().all():
        event_result = await db.execute(
            select(ResearchEvent)
            .where(ResearchEvent.study_id == config.id)
            .order_by(ResearchEvent.recorded_at.asc())
        )
        events = [
            ExportEvent(
                event_type=e.event_type,
                group=e.event_data.get("group"),
                event_data={
                    k: v
                    for k, v in e.event_data.items()
                    if k not in ("student_id", "student_name", "email")
                },
                recorded_at=e.recorded_at.isoformat(),
            )
            for e in event_result.scalars().all()
        ]
        results.append(
            StudyExportResponse(
                study_id=str(config.id),
                study_name=config.study_name,
                events=events,
            )
        )
    return results
