"""Process verification models: interaction scores."""

import uuid
from datetime import datetime

from sqlalchemy import Float, ForeignKey, Integer, String, DateTime, Index, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from docere.models.base import Base, UUIDMixin


class InteractionScore(Base, UUIDMixin):
    """Process verification score for a single tutoring interaction."""

    __tablename__ = "interaction_scores"
    __table_args__ = (
        Index("idx_interaction_scores_student", "student_id", "scored_at"),
        Index("idx_interaction_scores_conversation", "conversation_id"),
    )

    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id", ondelete="CASCADE"), nullable=False
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # Process reward model scores
    helpfulness_score: Mapped[float | None] = mapped_column(Float)
    clarity_score: Mapped[float | None] = mapped_column(Float)
    engagement_score: Mapped[float | None] = mapped_column(Float)
    understanding_delta: Mapped[float | None] = mapped_column(Float)

    # Evidence signals
    student_followup_type: Mapped[str | None] = mapped_column(String(50))
    time_to_next_message_seconds: Mapped[int | None] = mapped_column(Integer)
    subsequent_performance: Mapped[float | None] = mapped_column(Float)

    # Composite
    composite_score: Mapped[float | None] = mapped_column(Float)
    scoring_method: Mapped[str | None] = mapped_column(String(50))
    scoring_metadata: Mapped[dict] = mapped_column(JSONB, default=dict)

    scored_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    message: Mapped["Message"] = relationship(back_populates="interaction_score")  # type: ignore[name-defined]  # noqa: F821
