"""Research study models: study config and event logging."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from docere.models.base import Base, UUIDMixin


class StudyConfig(Base, UUIDMixin):
    """Configuration for an ablation study."""

    __tablename__ = "study_config"

    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )
    study_name: Mapped[str | None] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    groups: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    randomization_seed: Mapped[int | None] = mapped_column(Integer)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ResearchEvent(Base, UUIDMixin):
    """Research event log for the ablation study."""

    __tablename__ = "research_events"
    __table_args__ = (
        Index("idx_research_events", "study_id", "student_id", "event_type", "recorded_at"),
    )

    study_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("study_config.id"), nullable=False
    )
    student_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    event_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
