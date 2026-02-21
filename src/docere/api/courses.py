"""Course management endpoints."""

import uuid

from fastapi import APIRouter, Depends
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


@router.get("/{course_id}")
async def get_course(course_id: str) -> dict[str, str]:
    """Get course details including syllabus and materials."""
    # TODO: Return course with auto-pulled LMS content
    return {"status": "not_implemented"}


@router.post("/{course_id}/sync")
async def trigger_sync(course_id: str) -> dict[str, str]:
    """Manually trigger LMS sync for a course."""
    # TODO: Queue LMS sync task
    return {"status": "not_implemented"}


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


@router.post("/{course_id}/materials")
async def add_supplementary_material(course_id: str) -> dict[str, str]:
    """Optional: add supplementary materials not in the LMS."""
    # TODO: Accept and embed supplementary materials
    return {"status": "not_implemented"}
