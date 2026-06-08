"""Course management endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from docere.dependencies import get_current_user_id, get_db
from docere.models.course import Course, CourseMaterial, Enrollment
from docere.models.lti_platform import LTIPlatform
from docere.models.user import User
from docere.services.lti_service import create_adapter, sync_user_enrollments

router = APIRouter()
logger = structlog.get_logger()


class CourseResponse(BaseModel):
    id: uuid.UUID
    name: str
    course_code: str | None = None

    model_config = {"from_attributes": True}


@router.get("/", response_model=list[CourseResponse])
async def list_courses(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[Course]:
    """List courses the current user is enrolled in.

    If the user has an LMS link, auto-discovers and syncs their courses
    from the LMS so newly-added courses appear without a fresh LTI launch.
    """
    # If the user has an LMS link, discover any missing courses/enrollments
    user = await db.get(User, user_id)
    if user and user.external_lms_id and user.lms_platform:
        await _discover_lms_courses(db, user)

    # Query enrolled courses
    enrolled_query = (
        select(Course)
        .join(Enrollment, Enrollment.course_id == Course.id)
        .where(Enrollment.user_id == user_id)
        .order_by(Course.name)
    )
    result = await db.execute(enrolled_query)
    courses = list(result.scalars().all())

    # Fallback: if no enrollments, return all courses (dev convenience)
    if not courses:
        all_query = select(Course).order_by(Course.name)
        result = await db.execute(all_query)
        courses = list(result.scalars().all())

    return courses


async def _discover_lms_courses(db: AsyncSession, user: User) -> None:
    """Check the user's LMS for courses and sync any missing enrollments."""
    try:
        platform_result = await db.execute(
            select(LTIPlatform).where(
                LTIPlatform.id == uuid.UUID(user.lms_platform),
                LTIPlatform.is_active.is_(True),
            )
        )
        platform = platform_result.scalar_one_or_none()
        if not platform or not platform.api_base_url or not platform.api_token:
            return

        adapter = create_adapter(platform)
        await sync_user_enrollments(db, user, adapter, platform)
        await db.commit()
    except Exception:
        logger.warning(
            "LMS course discovery failed",
            user_id=str(user.id),
            exc_info=True,
        )


class CourseDetailResponse(BaseModel):
    id: str
    name: str
    course_code: str | None = None
    term: str | None = None
    syllabus_text: str | None = None
    lms_platform: str | None = None
    student_count: int = 0
    material_count: int = 0
    assignment_count: int = 0
    last_synced_at: str | None = None


@router.get("/{course_id}", response_model=CourseDetailResponse)
async def get_course(
    course_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> CourseDetailResponse:
    """Get course details including syllabus and materials."""
    from sqlalchemy import func

    course = await db.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    # Counts
    student_count_r = await db.execute(
        select(func.count(Enrollment.id)).where(
            Enrollment.course_id == course_id,
            Enrollment.lms_role == "student",
        )
    )
    material_count_r = await db.execute(
        select(func.count(CourseMaterial.id)).where(
            CourseMaterial.course_id == course_id,
        )
    )
    from docere.models.course import Assignment

    assignment_count_r = await db.execute(
        select(func.count(Assignment.id)).where(
            Assignment.course_id == course_id,
        )
    )

    return CourseDetailResponse(
        id=str(course.id),
        name=course.name,
        course_code=course.course_code,
        term=course.term,
        syllabus_text=course.syllabus_text,
        lms_platform=course.lms_platform,
        student_count=student_count_r.scalar() or 0,
        material_count=material_count_r.scalar() or 0,
        assignment_count=assignment_count_r.scalar() or 0,
        last_synced_at=(course.last_synced_at.isoformat() if course.last_synced_at else None),
    )


class SyncResponse(BaseModel):
    status: str
    message: str


@router.post("/{course_id}/sync", response_model=SyncResponse)
async def trigger_sync(
    course_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> SyncResponse:
    """Manually trigger LMS sync for a course."""
    course = await db.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    if not course.external_lms_id or not course.lms_platform:
        return SyncResponse(
            status="skipped",
            message="Course is not linked to an LMS",
        )

    try:
        from docere.services.lms_sync_service import LMSSyncService

        sync_svc = LMSSyncService(db)
        await sync_svc.full_sync(course)
        await db.commit()
        return SyncResponse(status="ok", message="Sync completed")
    except Exception as e:
        logger.warning("LMS sync failed", error=str(e))
        return SyncResponse(status="error", message=f"Sync failed: {e}")


class MaterialResponse(BaseModel):
    id: uuid.UUID
    title: str | None = None
    material_type: str

    model_config = {"from_attributes": True}


@router.get("/{course_id}/assignments", response_model=list[MaterialResponse])
async def list_assignments(
    course_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[CourseMaterial]:
    """List assignments and quizzes for a course (auto-synced from LMS)."""
    result = await db.execute(
        select(CourseMaterial)
        .where(
            CourseMaterial.course_id == course_id,
            CourseMaterial.material_type.in_(["assign", "quiz"]),
            CourseMaterial.title.isnot(None),
        )
        .order_by(CourseMaterial.title)
    )
    return list(result.scalars().all())


class UploadMaterialResponse(BaseModel):
    id: str
    title: str | None = None
    material_type: str
    status: str


@router.post(
    "/{course_id}/materials",
    response_model=UploadMaterialResponse,
)
async def add_supplementary_material(
    course_id: uuid.UUID,
    title: str | None = None,
    material_type: str = "supplement",
    content: str = "",
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> UploadMaterialResponse:
    """Add supplementary materials not in the LMS."""
    course = await db.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    import hashlib

    material = CourseMaterial(
        course_id=course_id,
        material_type=material_type,
        title=title,
        content=content,
        content_hash=hashlib.sha256(content.encode()).hexdigest(),
    )
    db.add(material)
    await db.commit()
    await db.refresh(material)

    return UploadMaterialResponse(
        id=str(material.id),
        title=material.title,
        material_type=material.material_type,
        status="created",
    )
