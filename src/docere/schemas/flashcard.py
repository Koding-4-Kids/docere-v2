"""Flashcard review request/response schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class FlashcardCardResponse(BaseModel):
    id: uuid.UUID
    front: str
    back: str
    concepts: list[str] | None = None
    state: str
    due_at: datetime
    reps: int
    lapses: int

    model_config = {"from_attributes": True}


class ReviewSessionResponse(BaseModel):
    cards: list[FlashcardCardResponse]
    total_due: int
    deck_id: uuid.UUID


class ReviewRequest(BaseModel):
    rating: int = Field(..., ge=1, le=4)
    review_duration_ms: int | None = None


class ReviewResponse(BaseModel):
    card_id: uuid.UUID
    new_state: str
    new_due_at: datetime
    scheduled_days: float


class UndoResponse(BaseModel):
    card_id: uuid.UUID
    restored_state: str
    restored_due_at: datetime


class DueCountResponse(BaseModel):
    course_id: str
    due_count: int
