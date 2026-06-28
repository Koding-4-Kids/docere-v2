"""Learning analytics event model."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from docere.models.base import Base, UUIDMixin


class LearningAnalyticsEvent(Base, UUIDMixin):
    """A learning analytics event (interaction, grade change, login, etc)."""

    __tablename__ = "learning_analytics_events"
    __table_args__ = (
        Index("idx_analytics_student_course", "student_id", "course_id", "event_type"),
        Index("idx_analytics_time", "recorded_at"),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    course_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("courses.id")
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    event_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
