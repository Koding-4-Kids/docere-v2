"""Student profile endpoints (instructor view)."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/courses/{course_id}/students")
async def list_students(course_id: str) -> dict[str, str]:
    """List enrolled students with profile summaries."""
    # TODO: Return students with risk levels, last active, mastery overview
    return {"status": "not_implemented"}


@router.get("/courses/{course_id}/students/{student_id}/profile")
async def get_student_profile(course_id: str, student_id: str) -> dict[str, str]:
    """Get detailed student profile with memory summary."""
    # TODO: Return full profile, concept mastery, interaction history summary
    return {"status": "not_implemented"}


@router.get("/courses/{course_id}/students/{student_id}/memories")
async def get_student_memories(course_id: str, student_id: str) -> dict[str, str]:
    """View student's memory tree (struggles, breakthroughs, patterns)."""
    # TODO: Return structured memory records
    return {"status": "not_implemented"}


@router.get("/courses/{course_id}/students/{student_id}/interactions")
async def get_student_interactions(course_id: str, student_id: str) -> dict[str, str]:
    """View interaction history with process verification scores."""
    # TODO: Return interactions with helpfulness/clarity/understanding scores
    return {"status": "not_implemented"}
