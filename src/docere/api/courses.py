"""Course management endpoints."""

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from docere.dependencies import get_current_user_id, get_db
from docere.models.course import Course, Enrollment

router = APIRouter()


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

    In dev mode, returns all courses (since enrollment may not be set up).
    """
    # First try enrolled courses
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


@router.get("/{course_id}/assignments")
async def list_assignments(course_id: str) -> dict[str, str]:
    """List assignments (auto-synced from LMS)."""
    # TODO: Return assignments from database
    return {"status": "not_implemented"}


@router.post("/{course_id}/materials")
async def add_supplementary_material(course_id: str) -> dict[str, str]:
    """Optional: add supplementary materials not in the LMS."""
    # TODO: Accept and embed supplementary materials
    return {"status": "not_implemented"}
