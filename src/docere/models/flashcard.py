"""Flashcard spaced repetition models."""

import hashlib
import uuid
from datetime import datetime

from sqlalchemy import (
    ARRAY,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from docere.models.base import Base, UUIDMixin


class FlashcardDeck(Base, UUIDMixin):
    """One deck per student per course. Auto-created when first cards are added."""

    __tablename__ = "flashcard_decks"
    __table_args__ = (
        UniqueConstraint("student_id", "course_id", name="uq_deck_student_course"),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False, default="Flashcards")
    card_count: Mapped[int] = mapped_column(Integer, default=0)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    cards: Mapped[list["FlashcardCard"]] = relationship(
        back_populates="deck", cascade="all, delete-orphan"
    )


class FlashcardCard(Base, UUIDMixin):
    """Individual flashcard with FSRS scheduling state."""

    __tablename__ = "flashcard_cards"
    __table_args__ = (
        Index("idx_card_deck", "deck_id"),
        Index("idx_card_due", "student_id", "due_at"),
        UniqueConstraint("deck_id", "front_hash", name="uq_card_front_per_deck"),
    )

    deck_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("flashcard_decks.id", ondelete="CASCADE"), nullable=False
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    front: Mapped[str] = mapped_column(Text, nullable=False)
    back: Mapped[str] = mapped_column(Text, nullable=False)
    front_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source_message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id")
    )
    concepts: Mapped[list[str] | None] = mapped_column(ARRAY(String))

    # FSRS v6 state — full Card object serialized as JSONB
    fsrs_state: Mapped[dict] = mapped_column(JSONB, default=dict)
    # Denormalized for efficient SQL queries
    due_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    stability: Mapped[float] = mapped_column(Float, default=0.0)
    difficulty: Mapped[float] = mapped_column(Float, default=0.0)
    reps: Mapped[int] = mapped_column(Integer, default=0)
    lapses: Mapped[int] = mapped_column(Integer, default=0)
    state: Mapped[str] = mapped_column(String(20), default="new")
    is_suspended: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    deck: Mapped["FlashcardDeck"] = relationship(back_populates="cards")
    reviews: Mapped[list["CardReview"]] = relationship(
        back_populates="card", cascade="all, delete-orphan"
    )

    @staticmethod
    def hash_front(front: str) -> str:
        normalized = " ".join(front.lower().split())
        return hashlib.sha256(normalized.encode()).hexdigest()


class CardReview(Base, UUIDMixin):
    """Audit trail of every card review."""

    __tablename__ = "card_reviews"
    __table_args__ = (
        Index("idx_review_card", "card_id", "reviewed_at"),
        Index("idx_review_student", "student_id", "reviewed_at"),
    )

    card_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("flashcard_cards.id", ondelete="CASCADE"), nullable=False
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    review_duration_ms: Mapped[int | None] = mapped_column(Integer)
    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    scheduled_days: Mapped[float] = mapped_column(Float, default=0.0)
    elapsed_days: Mapped[float] = mapped_column(Float, default=0.0)

    card: Mapped["FlashcardCard"] = relationship(back_populates="reviews")
