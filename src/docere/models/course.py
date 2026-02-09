"""Course, enrollment, assignment, and submission models."""

import uuid
from datetime import datetime

from sqlalchemy import Float, ForeignKey, Integer, String, Text, Boolean, UniqueConstraint, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from docere.models.base import Base, TimestampMixin, UUIDMixin


class Course(Base, UUIDMixin, TimestampMixin):
    """Course - auto-synced from Canvas/Moodle."""

    __tablename__ = "courses"
    __table_args__ = (
        UniqueConstraint("external_lms_id", "lms_platform", name="uq_course_lms"),
    )

    external_lms_id: Mapped[str | None] = mapped_column(String(255))
    lms_platform: Mapped[str | None] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    course_code: Mapped[str | None] = mapped_column(String(100))
    instructor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    syllabus_text: Mapped[str | None] = mapped_column(Text)
    syllabus_embedding_id: Mapped[str | None] = mapped_column(String(255))
    term: Mapped[str | None] = mapped_column(String(100))
    lms_sync_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    enrollments: Mapped[list["Enrollment"]] = relationship(back_populates="course")
    assignments: Mapped[list["Assignment"]] = relationship(back_populates="course")
    materials: Mapped[list["CourseMaterial"]] = relationship(back_populates="course")


class Enrollment(Base, UUIDMixin):
    """Student enrollment in a course."""

    __tablename__ = "enrollments"
    __table_args__ = (
        UniqueConstraint("user_id", "course_id", name="uq_enrollment"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )
    lms_role: Mapped[str] = mapped_column(String(50), default="student")
    study_group: Mapped[str | None] = mapped_column(String(50))
    enrolled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="enrollments")  # type: ignore[name-defined]  # noqa: F821
    course: Mapped["Course"] = relationship(back_populates="enrollments")


class Assignment(Base, UUIDMixin, TimestampMixin):
    """Assignment - auto-synced from LMS."""

    __tablename__ = "assignments"

    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )
    external_lms_id: Mapped[str | None] = mapped_column(String(255))
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    points_possible: Mapped[float | None] = mapped_column(Float)
    assignment_type: Mapped[str | None] = mapped_column(String(100))

    # Relationships
    course: Mapped["Course"] = relationship(back_populates="assignments")
    submissions: Mapped[list["Submission"]] = relationship(back_populates="assignment")


class Submission(Base, UUIDMixin):
    """Student submission/grade - auto-synced from LMS."""

    __tablename__ = "submissions"

    assignment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    external_lms_id: Mapped[str | None] = mapped_column(String(255))
    score: Mapped[float | None] = mapped_column(Float)
    grade: Mapped[str | None] = mapped_column(String(20))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    graded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    workflow_state: Mapped[str] = mapped_column(String(50), default="submitted")
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    assignment: Mapped["Assignment"] = relationship(back_populates="submissions")


class CourseMaterial(Base, UUIDMixin):
    """Course material - auto-pulled from LMS (syllabus, lectures, files)."""

    __tablename__ = "course_materials"

    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )
    external_lms_id: Mapped[str | None] = mapped_column(String(255))
    material_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str | None] = mapped_column(String(500))
    content: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str | None] = mapped_column(String(64))
    source_url: Mapped[str | None] = mapped_column(Text)
    embedding_id: Mapped[str | None] = mapped_column(String(255))
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    course: Mapped["Course"] = relationship(back_populates="materials")
