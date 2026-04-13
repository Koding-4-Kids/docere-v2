"""Teaching strategy models for the self-improvement loop."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from docere.models.base import Base, UUIDMixin


class Strategy(Base, UUIDMixin):
    """A teaching strategy in the archive."""

    __tablename__ = "strategies"

    name: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    strategy_type: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_template: Mapped[str] = mapped_column(Text, nullable=False)
    applicable_contexts: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Performance tracking
    total_uses: Mapped[int] = mapped_column(Integer, default=0)
    avg_score: Mapped[float | None] = mapped_column(Float)
    success_rate: Mapped[float | None] = mapped_column(Float)
    confidence_interval: Mapped[float | None] = mapped_column(Float)

    # Evolution lineage
    parent_strategy_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("strategies.id")
    )
    generation: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_baseline: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class StrategyScore(Base, UUIDMixin):
    """Score for a strategy used in a specific interaction."""

    __tablename__ = "strategy_scores"
    __table_args__ = (Index("idx_strategy_scores_strategy", "strategy_id", "recorded_at"),)

    strategy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("strategies.id", ondelete="CASCADE"), nullable=False
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id")
    )
    interaction_score_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("interaction_scores.id")
    )
    score: Mapped[float] = mapped_column(Float, nullable=False)
    context_metadata: Mapped[dict] = mapped_column(JSONB, default=dict)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
