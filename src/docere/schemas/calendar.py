"""Pydantic schemas for calendar/meeting endpoints."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class OAuthAuthorizeResponse(BaseModel):
    url: str


class OAuthCallbackResponse(BaseModel):
    connected: bool
    message: str


class CalendarStatusResponse(BaseModel):
    connected: bool
    calendar_id: str | None = None


class OfficeHoursCreate(BaseModel):
    day_of_week: int = Field(..., ge=0, le=6, description="0=Monday, 6=Sunday")
    start_time: str = Field(..., pattern=r"^\d{2}:\d{2}$", description="HH:MM")
    end_time: str = Field(..., pattern=r"^\d{2}:\d{2}$", description="HH:MM")
    timezone: str = "America/New_York"
    slot_duration_minutes: int = 30


class OfficeHoursResponse(BaseModel):
    id: uuid.UUID
    course_id: uuid.UUID
    day_of_week: int
    start_time: str
    end_time: str
    timezone: str
    slot_duration_minutes: int
    is_active: bool

    model_config = {"from_attributes": True}


class TimeSlotResponse(BaseModel):
    start: str  # ISO datetime
    end: str
    instructor_id: str


class BookMeetingRequest(BaseModel):
    instructor_id: uuid.UUID
    slot_start: datetime
    slot_end: datetime
    conversation_id: uuid.UUID | None = None


class MeetingResponse(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    instructor_id: uuid.UUID
    course_id: uuid.UUID
    conversation_id: uuid.UUID | None = None
    scheduled_start: datetime
    scheduled_end: datetime
    status: str
    context_summary: str | None = None
    struggle_concepts: list[str] | None = None
    google_event_id: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class MeetingAction(BaseModel):
    """An action block extracted from agent response (meeting suggestion)."""

    type: Literal["meeting_suggestion"]
    reason: str
    concepts: list[str] = []
