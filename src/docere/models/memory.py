"""Memory and student profile models."""

import uuid
from datetime import datetime
from typing import Any

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
from sqlalchemy.orm import Mapped, mapped_column

from docere.models.base import Base, UUIDMixin


class MemoryRecord(Base, UUIDMixin):
    """A single memory record (question, struggle, breakthrough, insight)."""

    __tablename__ = "memory_records"
    __table_args__ = (
        Index("idx_memory_student_course", "student_id", "course_id", "memory_type"),
        Index("idx_memory_created", "created_at"),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )
    memory_type: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_id: Mapped[str | None] = mapped_column(String(255))
    concepts: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    sentiment: Mapped[str | None] = mapped_column(String(50))
    confusion_score: Mapped[float] = mapped_column(Float, default=0.0)
    source: Mapped[str | None] = mapped_column(String(100))
    source_message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id")
    )
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)
    is_compressed: Mapped[bool] = mapped_column(Boolean, default=False)
    compressed_into: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class StudentProfile(Base, UUIDMixin):
    """Aggregate student profile for a course."""

    __tablename__ = "student_profiles"
    __table_args__ = (UniqueConstraint("student_id", "course_id", name="uq_student_profile"),)

    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )
    total_interactions: Mapped[int] = mapped_column(Integer, default=0)
    total_messages: Mapped[int] = mapped_column(Integer, default=0)
    avg_confusion_score: Mapped[float] = mapped_column(Float, default=0.0)
    avg_interaction_score: Mapped[float] = mapped_column(Float, default=0.0)
    engagement_level: Mapped[str] = mapped_column(String(50), default="unknown")
    current_grade: Mapped[float | None] = mapped_column(Float)
    last_interaction_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    avg_session_duration_minutes: Mapped[float | None] = mapped_column(Float)
    preferred_interaction_times: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    profile_summary: Mapped[str | None] = mapped_column(Text)
    profile_embedding_id: Mapped[str | None] = mapped_column(String(255))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ConceptMastery(Base, UUIDMixin):
    """Per-concept skill tracking for a student."""

    __tablename__ = "concept_mastery"
    __table_args__ = (
        UniqueConstraint("student_id", "course_id", "concept_name", name="uq_concept_mastery"),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )
    concept_name: Mapped[str] = mapped_column(String(255), nullable=False)
    mastery_level: Mapped[float] = mapped_column(Float, default=0.0)
    times_practiced: Mapped[int] = mapped_column(Integer, default=0)
    times_struggled: Mapped[int] = mapped_column(Integer, default=0)
    last_practiced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    evidence: Mapped[list[Any] | None] = mapped_column(JSONB, default=list)
