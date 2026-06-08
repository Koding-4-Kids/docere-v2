"""Calendar integration endpoints: OAuth, office hours, availability, booking."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from docere.dependencies import get_current_user_id, get_db, require_instructor
from docere.models.calendar import MeetingRequest, OfficeHours
from docere.models.memory import StudentProfile
from docere.schemas.calendar import (
    BookMeetingRequest,
    CalendarStatusResponse,
    MeetingResponse,
    OAuthAuthorizeResponse,
    OfficeHoursCreate,
    OfficeHoursResponse,
    TimeSlotResponse,
)
from docere.services.availability_service import AvailabilityService
from docere.services.google_calendar import GoogleCalendarService

router = APIRouter()


# ── Google OAuth ──


@router.get("/oauth/authorize", response_model=OAuthAuthorizeResponse)
async def authorize_google_calendar(
    user_id: uuid.UUID = Depends(require_instructor),
    db: AsyncSession = Depends(get_db),
) -> OAuthAuthorizeResponse:
    """Get Google OAuth2 authorization URL for calendar access."""
    gcal = GoogleCalendarService(db)
    url = gcal.get_authorization_url(state=str(user_id))
    return OAuthAuthorizeResponse(url=url)


@router.get("/oauth/callback")
async def oauth_callback(
    code: str = Query(...),
    state: str = Query(""),
    error: str = Query(None),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    """Handle Google OAuth2 callback — exchange code for tokens.

    Returns an HTML page that notifies the opener window and closes itself.
    """
    if error:
        return _oauth_result_page(success=False, message=f"OAuth error: {error}")
    if not state:
        return _oauth_result_page(success=False, message="Missing state parameter")

    try:
        gcal = GoogleCalendarService(db)
        await gcal.handle_oauth_callback(code=code, instructor_id=state)
        return _oauth_result_page(success=True, message="Google Calendar connected!")
    except Exception as e:
        import structlog

        structlog.get_logger().error("OAuth callback failed", error=str(e), state=state)
        return _oauth_result_page(success=False, message="Failed to connect. Please try again.")


def _oauth_result_page(success: bool, message: str) -> HTMLResponse:
    """Return a small HTML page that posts result to the opener and auto-closes."""
    status = "success" if success else "error"
    return HTMLResponse(f"""<!DOCTYPE html>
<html><head><title>Docere - Google Auth</title></head>
<body style="display:flex;align-items:center;justify-content:center;height:100vh;
  font-family:system-ui;background:#111;color:#fff">
  <p>{message}</p>
  <script>
    if (window.opener) {{
      window.opener.postMessage({{ type: "google-oauth-callback", status: "{status}" }}, "*");
    }}
    setTimeout(function() {{ window.close(); }}, 1500);
  </script>
</body></html>""")


@router.get("/oauth/upgrade-scopes", response_model=OAuthAuthorizeResponse)
async def upgrade_google_scopes(
    user_id: uuid.UUID = Depends(require_instructor),
    db: AsyncSession = Depends(get_db),
) -> OAuthAuthorizeResponse:
    """Re-authorize with expanded Google scopes (adds Gmail, Docs, Sheets)."""
    gcal = GoogleCalendarService(db)
    url = gcal.get_authorization_url(state=str(user_id))
    return OAuthAuthorizeResponse(url=url)


@router.get("/status", response_model=CalendarStatusResponse)
async def get_calendar_status(
    user_id: uuid.UUID = Depends(require_instructor),
    db: AsyncSession = Depends(get_db),
) -> CalendarStatusResponse:
    """Check if instructor has connected their Google Calendar."""
    gcal = GoogleCalendarService(db)
    connected = await gcal.has_calendar_connected(str(user_id))
    return CalendarStatusResponse(connected=connected)


@router.delete("/disconnect")
async def disconnect_calendar(
    user_id: uuid.UUID = Depends(require_instructor),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Disconnect Google Calendar (deactivate tokens)."""
    from docere.models.calendar import InstructorCalendarToken

    result = await db.execute(
        select(InstructorCalendarToken).where(InstructorCalendarToken.instructor_id == user_id)
    )
    token = result.scalar_one_or_none()
    if token:
        token.is_active = False
        await db.commit()
    return {"status": "disconnected"}


# ── Office Hours ──


@router.post("/office-hours/{course_id}", response_model=OfficeHoursResponse)
async def create_office_hours(
    course_id: uuid.UUID,
    request: OfficeHoursCreate,
    user_id: uuid.UUID = Depends(require_instructor),
    db: AsyncSession = Depends(get_db),
) -> OfficeHours:
    """Create a recurring office hours block for a course."""
    oh = OfficeHours(
        instructor_id=user_id,
        course_id=course_id,
        day_of_week=request.day_of_week,
        start_time=request.start_time,
        end_time=request.end_time,
        timezone=request.timezone,
        slot_duration_minutes=request.slot_duration_minutes,
    )
    db.add(oh)
    await db.commit()
    await db.refresh(oh)
    return oh


@router.get("/office-hours/{course_id}", response_model=list[OfficeHoursResponse])
async def list_office_hours(
    course_id: uuid.UUID,
    user_id: uuid.UUID = Depends(require_instructor),
    db: AsyncSession = Depends(get_db),
) -> list[OfficeHours]:
    """List office hours for a course."""
    result = await db.execute(
        select(OfficeHours).where(
            OfficeHours.instructor_id == user_id,
            OfficeHours.course_id == course_id,
            OfficeHours.is_active == True,  # noqa: E712
        )
    )
    return list(result.scalars().all())


@router.delete("/office-hours/{office_hours_id}", status_code=204)
async def delete_office_hours(
    office_hours_id: uuid.UUID,
    user_id: uuid.UUID = Depends(require_instructor),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove an office hours block."""
    result = await db.execute(
        select(OfficeHours).where(
            OfficeHours.id == office_hours_id,
            OfficeHours.instructor_id == user_id,
        )
    )
    oh = result.scalar_one_or_none()
    if not oh:
        raise HTTPException(status_code=404, detail="Office hours not found")
    oh.is_active = False
    await db.commit()


# ── Availability & Booking ──


@router.get("/available-slots/{course_id}", response_model=list[TimeSlotResponse])
async def get_available_slots(
    course_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Get available meeting slots for a course (student-facing)."""
    svc = AvailabilityService(db)
    return await svc.get_available_slots(course_id=str(course_id))


@router.post("/book/{course_id}", response_model=MeetingResponse)
async def book_meeting(
    course_id: uuid.UUID,
    request: BookMeetingRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> MeetingRequest:
    """Book a meeting slot with an instructor."""
    # Generate context summary from student profile
    profile_result = await db.execute(
        select(StudentProfile).where(
            StudentProfile.student_id == user_id,
            StudentProfile.course_id == course_id,
        )
    )
    profile = profile_result.scalar_one_or_none()

    struggle_concepts = []
    context_summary = "Student requested a meeting."

    if profile:
        # Get top struggling concepts from concept mastery
        from docere.models.memory import ConceptMastery

        mastery_result = await db.execute(
            select(ConceptMastery)
            .where(
                ConceptMastery.student_id == user_id,
                ConceptMastery.course_id == course_id,
            )
            .order_by(ConceptMastery.times_struggled.desc())
            .limit(5)
        )
        masteries = mastery_result.scalars().all()
        struggle_concepts = [m.concept_name for m in masteries if m.times_struggled > 0]

        context_summary = (
            f"Student has {profile.total_interactions} total interactions. "
            f"Average confusion: {profile.avg_confusion_score:.2f}. "
            f"Engagement: {profile.engagement_level}."
        )
        if struggle_concepts:
            context_summary += f" Struggling with: {', '.join(struggle_concepts)}."

    svc = AvailabilityService(db)
    meeting = await svc.book_meeting(
        student_id=str(user_id),
        instructor_id=str(request.instructor_id),
        course_id=str(course_id),
        slot_start=request.slot_start,
        slot_end=request.slot_end,
        context_summary=context_summary,
        struggle_concepts=struggle_concepts,
        conversation_id=str(request.conversation_id) if request.conversation_id else None,
    )
    return meeting


@router.get("/meetings/{course_id}", response_model=list[MeetingResponse])
async def list_meetings(
    course_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[MeetingRequest]:
    """List meetings for a course (both student and instructor view)."""
    from sqlalchemy import or_

    result = await db.execute(
        select(MeetingRequest)
        .where(
            MeetingRequest.course_id == course_id,
            or_(
                MeetingRequest.student_id == user_id,
                MeetingRequest.instructor_id == user_id,
            ),
            MeetingRequest.status != "cancelled",
        )
        .order_by(MeetingRequest.scheduled_start)
    )
    return list(result.scalars().all())


@router.post("/meetings/{meeting_id}/cancel")
async def cancel_meeting(
    meeting_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Cancel a meeting."""
    svc = AvailabilityService(db)
    success = await svc.cancel_meeting(str(meeting_id), str(user_id))
    if not success:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return {"status": "cancelled"}
