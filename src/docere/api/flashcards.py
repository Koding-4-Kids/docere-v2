"""Flashcard spaced repetition API endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from docere.dependencies import get_db, get_current_user_id
from docere.schemas.flashcard import (
    DueCountResponse,
    FlashcardCardResponse,
    ReviewRequest,
    ReviewResponse,
    ReviewSessionResponse,
    UndoResponse,
)
from docere.services.flashcard_service import FlashcardService

router = APIRouter()


@router.get("/courses/{course_id}/review", response_model=ReviewSessionResponse)
async def get_review_session(
    course_id: uuid.UUID,
    limit: int = 20,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> ReviewSessionResponse:
    """Get due cards for a review session."""
    svc = FlashcardService(db)
    cards = await svc.get_due_cards(user_id, course_id, limit=limit)
    total_due = await svc.get_due_count(user_id, course_id)

    if not cards:
        # Return empty session — find deck ID or use a placeholder
        deck = await svc.get_or_create_deck(user_id, course_id)
        return ReviewSessionResponse(cards=[], total_due=0, deck_id=deck.id)

    return ReviewSessionResponse(
        cards=[
            FlashcardCardResponse(
                id=c.id,
                front=c.front,
                back=c.back,
                concepts=c.concepts,
                state=c.state,
                due_at=c.due_at,
                reps=c.reps,
                lapses=c.lapses,
            )
            for c in cards
        ],
        total_due=total_due,
        deck_id=cards[0].deck_id,
    )


@router.post("/cards/{card_id}/review", response_model=ReviewResponse)
async def review_card(
    card_id: uuid.UUID,
    request: ReviewRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> ReviewResponse:
    """Record a review and reschedule the card via FSRS."""
    svc = FlashcardService(db)
    try:
        card = await svc.review_card(
            card_id=card_id,
            student_id=user_id,
            rating=request.rating,
            review_duration_ms=request.review_duration_ms,
        )
    except Exception:
        raise HTTPException(status_code=404, detail="Card not found")

    await db.commit()
    return ReviewResponse(
        card_id=card.id,
        new_state=card.state,
        new_due_at=card.due_at,
        scheduled_days=0.0,
    )


@router.post("/cards/{card_id}/undo", response_model=UndoResponse)
async def undo_review(
    card_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> UndoResponse:
    """Undo the last review on a card."""
    svc = FlashcardService(db)
    card = await svc.undo_last_review(card_id, user_id)
    if not card:
        raise HTTPException(status_code=404, detail="No review to undo")

    await db.commit()
    return UndoResponse(
        card_id=card.id,
        restored_state=card.state,
        restored_due_at=card.due_at,
    )


@router.get("/due-counts", response_model=list[DueCountResponse])
async def get_due_counts(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[DueCountResponse]:
    """Get due card counts across all courses."""
    svc = FlashcardService(db)
    counts = await svc.get_all_due_counts(user_id)
    return [DueCountResponse(**c) for c in counts]
