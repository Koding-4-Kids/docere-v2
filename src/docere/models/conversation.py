"""Conversation and message models."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from docere.models.base import Base, UUIDMixin


class Conversation(Base, UUIDMixin):
    """A tutoring conversation between a student and the agent."""

    __tablename__ = "conversations"

    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )
    assignment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assignments.id")
    )
    title: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(50), default="active")
    strategy_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("strategies.id")
    )
    study_group: Mapped[str | None] = mapped_column(String(50))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_message_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    summarized: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    # Relationships
    student: Mapped["User"] = relationship(back_populates="conversations")  # type: ignore[name-defined]  # noqa: F821
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", order_by="Message.created_at"
    )


class Message(Base, UUIDMixin):
    """A single message in a conversation."""

    __tablename__ = "messages"
    __table_args__ = (
        Index("idx_messages_conversation", "conversation_id", "created_at"),
        Index("idx_messages_role", "conversation_id", "role"),
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_id: Mapped[str | None] = mapped_column(String(255))
    token_count: Mapped[int | None] = mapped_column(Integer)
    model_used: Mapped[str | None] = mapped_column(String(100))
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    @property
    def artifact(self) -> dict | None:
        """Extract study artifact from metadata for serialization."""
        meta = self.metadata_ or {}
        a = meta.get("artifact")
        return a if isinstance(a, dict) else None

    @property
    def action(self) -> dict | None:
        """Extract action (meeting suggestion) from metadata for serialization."""
        meta = self.metadata_ or {}
        a = meta.get("action")
        return a if isinstance(a, dict) else None

    @property
    def widgets(self) -> list[dict] | None:
        """Extract widget list from metadata for serialization."""
        meta = self.metadata_ or {}
        w = meta.get("widgets")
        return w if isinstance(w, list) else None

    # Relationships
    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
    interaction_score: Mapped["InteractionScore | None"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        back_populates="message", uselist=False
    )
