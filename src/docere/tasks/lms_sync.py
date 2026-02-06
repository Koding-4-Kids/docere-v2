"""Background task: periodic LMS sync (every 2 hours)."""

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from docere.models.course import Course
from docere.integrations.lms.canvas import CanvasAdapter
from docere.integrations.lms.moodle import MoodleAdapter
from docere.services.lms_sync_service import LMSSyncService

logger = structlog.get_logger()


async def sync_all_courses(db: AsyncSession) -> dict[str, int]:
    """Sync all LMS-enabled courses. Run every 2 hours via ARQ."""
    result = await db.execute(
        select(Course).where(Course.lms_sync_enabled.is_(True))
    )
    courses = result.scalars().all()

    synced = 0
    errors = 0

    for course in courses:
        try:
            if course.lms_platform == "canvas":
                adapter = CanvasAdapter()
            elif course.lms_platform == "moodle":
                adapter = MoodleAdapter()
            else:
                logger.warning("Unknown LMS platform", platform=course.lms_platform)
                continue

            service = LMSSyncService(db, adapter)
            await service.incremental_sync(course.id)
            synced += 1
            logger.info("Synced course", course_id=str(course.id), name=course.name)
        except Exception:
            errors += 1
            logger.exception("Failed to sync course", course_id=str(course.id))

    return {"synced": synced, "errors": errors}
