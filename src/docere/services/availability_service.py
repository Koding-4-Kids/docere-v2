"""Availability computation and meeting booking."""

from datetime import datetime, timedelta, timezone, time as dt_time
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from docere.config import settings
from docere.models.calendar import MeetingRequest, OfficeHours
from docere.models.course import Enrollment
from docere.models.user import User
from docere.services.google_calendar import GoogleCalendarService

logger = structlog.get_logger()


class AvailabilityService:
    """Computes available meeting slots and handles booking."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.gcal = GoogleCalendarService(db)

    async def get_available_slots(
        self,
        course_id: str,
        days_ahead: int = 7,
    ) -> list[dict]:
        """Get available meeting slots for a course's instructor.

        Combines office hours + Google Calendar free/busy - existing bookings.

        Returns list of {"start": iso, "end": iso, "instructor_id": str}
        """
        # Find instructor(s) for this course
        result = await self.db.execute(
            select(Enrollment).where(
                Enrollment.course_id == course_id,
                Enrollment.lms_role.in_(["instructor", "teacher", "ta"]),
            )
        )
        instructor_enrollments = result.scalars().all()
        if not instructor_enrollments:
            return []

        now = datetime.now(timezone.utc)
        end_date = now + timedelta(days=days_ahead)
        all_slots = []

        for enrollment in instructor_enrollments:
            instructor_id = str(enrollment.user_id)

            # Get office hours for this instructor + course
            oh_result = await self.db.execute(
                select(OfficeHours).where(
                    OfficeHours.instructor_id == enrollment.user_id,
                    OfficeHours.course_id == course_id,
                    OfficeHours.is_active == True,  # noqa: E712
                )
            )
            office_hours = oh_result.scalars().all()
            if not office_hours:
                continue

            # Generate candidate slots from office hours
            candidates = self._generate_slots_from_office_hours(
                office_hours, now, end_date
            )

            # Subtract Google Calendar busy times
            try:
                busy_periods = await self.gcal.get_free_busy(
                    instructor_id=instructor_id,
                    time_min=now,
                    time_max=end_date,
                )
            except Exception as e:
                logger.warning("Failed to check calendar", error=str(e))
                busy_periods = []

            # Subtract existing meeting bookings
            booking_result = await self.db.execute(
                select(MeetingRequest).where(
                    MeetingRequest.instructor_id == enrollment.user_id,
                    MeetingRequest.status == "confirmed",
                    MeetingRequest.scheduled_start >= now,
                    MeetingRequest.scheduled_end <= end_date,
                )
            )
            existing_bookings = booking_result.scalars().all()

            booked_periods = [
                {"start": b.scheduled_start.isoformat(), "end": b.scheduled_end.isoformat()}
                for b in existing_bookings
            ]

            available = self._subtract_busy(candidates, busy_periods + booked_periods)

            for slot in available:
                slot["instructor_id"] = instructor_id

            all_slots.extend(available)

        # Sort by start time
        all_slots.sort(key=lambda s: s["start"])
        return all_slots

    async def book_meeting(
        self,
        student_id: str,
        instructor_id: str,
        course_id: str,
        slot_start: datetime,
        slot_end: datetime,
        context_summary: str,
        struggle_concepts: list[str],
        conversation_id: str | None = None,
    ) -> MeetingRequest:
        """Book a meeting slot and create a Google Calendar event."""
        # Look up emails for the calendar invite
        student_result = await self.db.execute(
            select(User.email, User.name).where(User.id == student_id)
        )
        student_row = student_result.one_or_none()
        student_email = student_row.email if student_row else None
        student_name = student_row.name if student_row else "Student"

        instructor_result = await self.db.execute(
            select(User.name).where(User.id == instructor_id)
        )
        instructor_row = instructor_result.one_or_none()
        instructor_name = instructor_row.name if instructor_row else "Instructor"

        # Create Google Calendar event
        summary = f"Docere: {student_name} <> {instructor_name}"
        description = (
            f"Meeting scheduled via Docere\n\n"
            f"Student: {student_name}\n"
            f"Struggling with: {', '.join(struggle_concepts)}\n\n"
            f"Context:\n{context_summary}"
        )

        event_id = await self.gcal.create_event(
            instructor_id=instructor_id,
            summary=summary,
            description=description,
            start=slot_start,
            end=slot_end,
            attendee_email=student_email,
        )

        # Create meeting request record
        meeting = MeetingRequest(
            student_id=student_id,
            instructor_id=instructor_id,
            course_id=course_id,
            conversation_id=conversation_id,
            scheduled_start=slot_start,
            scheduled_end=slot_end,
            status="confirmed",
            context_summary=context_summary,
            struggle_concepts=struggle_concepts,
            google_event_id=event_id,
        )
        self.db.add(meeting)
        await self.db.commit()
        await self.db.refresh(meeting)

        logger.info(
            "Meeting booked",
            meeting_id=str(meeting.id),
            student_id=student_id,
            instructor_id=instructor_id,
        )
        return meeting

    async def cancel_meeting(self, meeting_id: str, cancelled_by: str) -> bool:
        """Cancel a meeting and remove from Google Calendar."""
        result = await self.db.execute(
            select(MeetingRequest).where(MeetingRequest.id == meeting_id)
        )
        meeting = result.scalar_one_or_none()
        if not meeting:
            return False

        # Cancel Google Calendar event
        if meeting.google_event_id:
            try:
                await self.gcal.cancel_event(
                    instructor_id=str(meeting.instructor_id),
                    event_id=meeting.google_event_id,
                )
            except Exception as e:
                logger.warning("Failed to cancel calendar event", error=str(e))

        meeting.status = "cancelled"
        await self.db.commit()

        logger.info("Meeting cancelled", meeting_id=meeting_id, cancelled_by=cancelled_by)
        return True

    def _generate_slots_from_office_hours(
        self,
        office_hours: list[OfficeHours],
        start: datetime,
        end: datetime,
    ) -> list[dict[str, str]]:
        """Generate concrete time slots from recurring office hours."""
        slots = []
        current_date = start.date()
        end_date = end.date()

        while current_date <= end_date:
            weekday = current_date.weekday()  # 0=Mon..6=Sun

            for oh in office_hours:
                if oh.day_of_week != weekday:
                    continue

                tz = ZoneInfo(oh.timezone)
                start_h, start_m = map(int, oh.start_time.split(":"))
                end_h, end_m = map(int, oh.end_time.split(":"))

                slot_start = datetime(
                    current_date.year, current_date.month, current_date.day,
                    start_h, start_m, tzinfo=tz,
                )
                block_end = datetime(
                    current_date.year, current_date.month, current_date.day,
                    end_h, end_m, tzinfo=tz,
                )
                duration = timedelta(minutes=oh.slot_duration_minutes)

                while slot_start + duration <= block_end:
                    slot_end = slot_start + duration
                    # Only include future slots
                    if slot_start > start:
                        slots.append({
                            "start": slot_start.astimezone(timezone.utc).isoformat(),
                            "end": slot_end.astimezone(timezone.utc).isoformat(),
                        })
                    slot_start = slot_end

            current_date += timedelta(days=1)

        return slots

    @staticmethod
    def _subtract_busy(
        candidates: list[dict[str, str]],
        busy_periods: list[dict[str, str]],
    ) -> list[dict[str, str]]:
        """Remove slots that overlap with any busy period."""
        if not busy_periods:
            return candidates

        busy_ranges = []
        for b in busy_periods:
            b_start = datetime.fromisoformat(b["start"])
            b_end = datetime.fromisoformat(b["end"])
            busy_ranges.append((b_start, b_end))

        available = []
        for slot in candidates:
            s_start = datetime.fromisoformat(slot["start"])
            s_end = datetime.fromisoformat(slot["end"])

            overlaps = any(
                s_start < b_end and s_end > b_start
                for b_start, b_end in busy_ranges
            )
            if not overlaps:
                available.append(slot)

        return available
