"""LMS sync and webhook endpoints."""

from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from docere.dependencies import get_db
from docere.models.analytics import LearningAnalyticsEvent
from docere.models.course import Course
from docere.models.user import User

router = APIRouter()
logger = structlog.get_logger()


class WebhookResponse(BaseModel):
    status: str
    events_processed: int = 0


@router.post("/webhooks/canvas", response_model=WebhookResponse)
async def canvas_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> WebhookResponse:
    """Canvas webhook receiver for real-time grade/submission updates."""
    try:
        body = await request.json()
    except Exception:
        return WebhookResponse(status="invalid_payload")

    events = body if isinstance(body, list) else [body]
    processed = 0

    for event in events:
        event_type = event.get("type", "unknown")
        canvas_course_id = event.get("course_id")
        canvas_user_id = event.get("user_id")

        # Resolve internal IDs
        course = None
        student = None
        if canvas_course_id:
            result = await db.execute(
                select(Course).where(
                    Course.external_lms_id == str(canvas_course_id),
                    Course.lms_platform == "canvas",
                )
            )
            course = result.scalar_one_or_none()

        if canvas_user_id:
            result = await db.execute(
                select(User).where(
                    User.external_lms_id == str(canvas_user_id),
                )
            )
            student = result.scalar_one_or_none()

        if not student:
            continue

        analytics_event = LearningAnalyticsEvent(
            student_id=student.id,
            course_id=course.id if course else None,
            event_type=f"canvas_{event_type}",
            event_data=event,
            recorded_at=datetime.now(UTC),
        )
        db.add(analytics_event)
        processed += 1

    if processed > 0:
        await db.commit()

    logger.info("Canvas webhook processed", events=processed)
    return WebhookResponse(status="received", events_processed=processed)


@router.post("/webhooks/moodle", response_model=WebhookResponse)
async def moodle_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> WebhookResponse:
    """Moodle event notification receiver."""
    try:
        body = await request.json()
    except Exception:
        return WebhookResponse(status="invalid_payload")

    events = body if isinstance(body, list) else [body]
    processed = 0

    for event in events:
        event_type = event.get("eventname", "unknown")
        moodle_course_id = event.get("courseid")
        moodle_user_id = event.get("userid") or event.get("relateduserid")

        # Resolve internal IDs
        course = None
        student = None
        if moodle_course_id:
            result = await db.execute(
                select(Course).where(
                    Course.external_lms_id == str(moodle_course_id),
                    Course.lms_platform == "moodle",
                )
            )
            course = result.scalar_one_or_none()

        if moodle_user_id:
            result = await db.execute(
                select(User).where(
                    User.external_lms_id == str(moodle_user_id),
                )
            )
            student = result.scalar_one_or_none()

        if not student:
            continue

        analytics_event = LearningAnalyticsEvent(
            student_id=student.id,
            course_id=course.id if course else None,
            event_type=f"moodle_{event_type}",
            event_data=event,
            recorded_at=datetime.now(UTC),
        )
        db.add(analytics_event)
        processed += 1

    if processed > 0:
        await db.commit()

    logger.info("Moodle webhook processed", events=processed)
    return WebhookResponse(status="received", events_processed=processed)
