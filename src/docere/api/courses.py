"""Course management endpoints."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_courses() -> dict[str, str]:
    """List courses for the current user (auto-synced from LMS)."""
    # TODO: Return courses from database (populated via LMS sync)
    return {"status": "not_implemented"}


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
