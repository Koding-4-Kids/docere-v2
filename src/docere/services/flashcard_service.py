"""Flashcard spaced repetition service — FSRS v6 scheduling + card management."""

import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from fsrs import Card, Rating, Scheduler
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from docere.models.flashcard import CardReview, FlashcardCard, FlashcardDeck

logger = structlog.get_logger()


class FlashcardService:
    """Manages flashcard decks, cards, and FSRS scheduling."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.fsrs = Scheduler()

    # ── Deck Management ──

    async def get_or_create_deck(
        self, student_id: uuid.UUID, course_id: uuid.UUID
    ) -> FlashcardDeck:
        result = await self.db.execute(
            select(FlashcardDeck).where(
                FlashcardDeck.student_id == student_id,
                FlashcardDeck.course_id == course_id,
            )
        )
        deck = result.scalar_one_or_none()
        if deck:
            return deck

        deck = FlashcardDeck(
            student_id=student_id,
            course_id=course_id,
            title="Flashcards",
        )
        self.db.add(deck)
        await self.db.flush()
        return deck

    # ── Card Management ──

    async def add_cards_from_artifact(
        self,
        student_id: uuid.UUID,
        course_id: uuid.UUID,
        cards_json: list[dict[str, Any]],
        source_message_id: uuid.UUID | None = None,
        concepts: list[str] | None = None,
    ) -> int:
        """Add cards from an agent-generated flashcard artifact. Deduplicates by front_hash."""
        deck = await self.get_or_create_deck(student_id, course_id)
        added = 0

        for card_data in cards_json:
            front = card_data.get("front", "").strip()
            back = card_data.get("back", "").strip()
            if not front or not back:
                continue

            front_hash = FlashcardCard.hash_front(front)

            existing = await self.db.execute(
                select(FlashcardCard.id).where(
                    FlashcardCard.deck_id == deck.id,
                    FlashcardCard.front_hash == front_hash,
                )
            )
            if existing.scalar_one_or_none():
                continue

            fsrs_card = Card()
            new_card = FlashcardCard(
                deck_id=deck.id,
                student_id=student_id,
                front=front,
                back=back,
                front_hash=front_hash,
                source_message_id=source_message_id,
                concepts=concepts,
                fsrs_state=fsrs_card.to_dict(),
                due_at=fsrs_card.due,
                stability=fsrs_card.stability or 0.0,
                difficulty=fsrs_card.difficulty or 0.0,
                reps=0,
                lapses=0,
                state=fsrs_card.state.name
                if hasattr(fsrs_card.state, "name")
                else str(fsrs_card.state),
            )
            self.db.add(new_card)
            added += 1

        if added:
            deck.card_count = (deck.card_count or 0) + added
            await self.db.flush()

        return added

    # ── Review Session ──

    async def get_due_cards(
        self, student_id: uuid.UUID, course_id: uuid.UUID, limit: int = 20
    ) -> list[FlashcardCard]:
        now = datetime.now(UTC)
        result = await self.db.execute(
            select(FlashcardCard)
            .join(FlashcardDeck)
            .where(
                FlashcardDeck.student_id == student_id,
                FlashcardDeck.course_id == course_id,
                FlashcardCard.is_suspended.is_(False),
                FlashcardCard.due_at <= now,
            )
            .order_by(FlashcardCard.reps.asc(), FlashcardCard.due_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_due_count(self, student_id: uuid.UUID, course_id: uuid.UUID) -> int:
        now = datetime.now(UTC)
        result = await self.db.execute(
            select(func.count(FlashcardCard.id))
            .join(FlashcardDeck)
            .where(
                FlashcardDeck.student_id == student_id,
                FlashcardDeck.course_id == course_id,
                FlashcardCard.is_suspended.is_(False),
                FlashcardCard.due_at <= now,
            )
        )
        return result.scalar() or 0

    async def get_all_due_counts(self, student_id: uuid.UUID) -> list[dict[str, Any]]:
        """Due counts across all enrolled courses."""
        now = datetime.now(UTC)
        result = await self.db.execute(
            select(
                FlashcardDeck.course_id,
                func.count(FlashcardCard.id).label("due_count"),
            )
            .join(FlashcardCard, FlashcardCard.deck_id == FlashcardDeck.id)
            .where(
                FlashcardDeck.student_id == student_id,
                FlashcardCard.is_suspended.is_(False),
                FlashcardCard.due_at <= now,
            )
            .group_by(FlashcardDeck.course_id)
        )
        return [
            {"course_id": str(row.course_id), "due_count": row.due_count} for row in result.all()
        ]

    # ── Review Card ──

    async def review_card(
        self,
        card_id: uuid.UUID,
        student_id: uuid.UUID,
        rating: int,
        review_duration_ms: int | None = None,
    ) -> FlashcardCard:
        result = await self.db.execute(
            select(FlashcardCard).where(
                FlashcardCard.id == card_id,
                FlashcardCard.student_id == student_id,
            )
        )
        card = result.scalar_one()

        fsrs_card = Card.from_dict(card.fsrs_state) if card.fsrs_state else Card()
        fsrs_rating = Rating(rating)
        now = datetime.now(UTC)
        updated_card, review_log = self.fsrs.review_card(fsrs_card, fsrs_rating, now)

        review = CardReview(
            card_id=card.id,
            student_id=student_id,
            rating=rating,
            review_duration_ms=review_duration_ms,
            reviewed_at=now,
            scheduled_days=0.0,
            elapsed_days=0.0,
        )
        self.db.add(review)

        _sync_card_from_fsrs(card, updated_card)

        # Update deck last_reviewed_at
        deck_result = await self.db.execute(
            select(FlashcardDeck).where(FlashcardDeck.id == card.deck_id)
        )
        deck = deck_result.scalar_one()
        deck.last_reviewed_at = now

        await self.db.flush()
        return card

    # ── Undo ──

    async def undo_last_review(
        self, card_id: uuid.UUID, student_id: uuid.UUID
    ) -> FlashcardCard | None:
        result = await self.db.execute(
            select(CardReview)
            .where(CardReview.card_id == card_id, CardReview.student_id == student_id)
            .order_by(CardReview.reviewed_at.desc())
            .limit(1)
        )
        last_review = result.scalar_one_or_none()
        if not last_review:
            return None

        card_result = await self.db.execute(
            select(FlashcardCard).where(FlashcardCard.id == card_id)
        )
        card = card_result.scalar_one()

        # Re-replay all reviews except the last to reconstruct FSRS state
        all_reviews_result = await self.db.execute(
            select(CardReview)
            .where(CardReview.card_id == card_id)
            .order_by(CardReview.reviewed_at.asc())
        )
        reviews = list(all_reviews_result.scalars().all())

        replayed = Card()
        for r in reviews[:-1]:
            replayed, _ = self.fsrs.review_card(replayed, Rating(r.rating), r.reviewed_at)

        _sync_card_from_fsrs(card, replayed)
        await self.db.delete(last_review)
        await self.db.flush()
        return card


# ── FSRS v6 Sync Helper ──


def _sync_card_from_fsrs(card: FlashcardCard, fsrs_card: Card) -> None:
    """Sync denormalized DB columns from an FSRS Card object."""
    card.fsrs_state = fsrs_card.to_dict()
    card.due_at = fsrs_card.due
    card.stability = fsrs_card.stability or 0.0
    card.difficulty = fsrs_card.difficulty or 0.0
    card.reps = fsrs_card.step or 0
    card.lapses = 0  # v6 doesn't track lapses; keep column for future use
    card.state = fsrs_card.state.name if hasattr(fsrs_card.state, "name") else str(fsrs_card.state)
