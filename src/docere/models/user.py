"""User model: students, instructors, admins."""

import uuid

from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from docere.models.base import Base, TimestampMixin, UUIDMixin


class User(Base, UUIDMixin, TimestampMixin):
    """User account - created automatically from LMS via LTI launch."""

    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("external_lms_id", "lms_platform", name="uq_user_lms"),
    )

    external_lms_id: Mapped[str | None] = mapped_column(String(255))
    lms_platform: Mapped[str | None] = mapped_column(String(50))
    email: Mapped[str | None] = mapped_column(String(255), unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="student")
    avatar_url: Mapped[str | None] = mapped_column(String(500))

    # Relationships
    enrollments: Mapped[list["Enrollment"]] = relationship(back_populates="user")  # type: ignore[name-defined]  # noqa: F821
    conversations: Mapped[list["Conversation"]] = relationship(back_populates="student")  # type: ignore[name-defined]  # noqa: F821
