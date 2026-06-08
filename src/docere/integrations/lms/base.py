"""Abstract LMS adapter interface.

Both Canvas and Moodle adapters implement this interface,
allowing the rest of the system to work with any LMS.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class LMSCourse:
    """Normalized course data from any LMS."""

    external_id: str
    name: str
    course_code: str
    syllabus_body: str | None = None
    term: str | None = None


@dataclass
class LMSAssignment:
    """Normalized assignment data from any LMS."""

    external_id: str
    title: str
    description: str | None = None
    due_at: str | None = None
    points_possible: float | None = None
    assignment_type: str | None = None


@dataclass
class LMSSubmission:
    """Normalized submission/grade data from any LMS."""

    external_id: str
    assignment_id: str
    student_id: str
    score: float | None = None
    grade: str | None = None
    submitted_at: str | None = None
    graded_at: str | None = None
    workflow_state: str = "submitted"


@dataclass
class LMSEnrollment:
    """Normalized enrollment data from any LMS."""

    user_id: str
    course_id: str
    role: str  # 'student' | 'teacher' | 'ta'
    name: str
    email: str | None = None


@dataclass
class LMSCourseMaterial:
    """Normalized course material (files, modules, etc)."""

    external_id: str
    title: str
    material_type: str  # 'file' | 'module' | 'page' | 'discussion' | 'quiz'
    content: str | None = None
    url: str | None = None
    file_urls: list[str] = field(default_factory=list)
    content_hash: str | None = None


@dataclass
class LMSFullSync:
    """Complete course data from a full LMS sync."""

    course: LMSCourse
    assignments: list[LMSAssignment] = field(default_factory=list)
    submissions: list[LMSSubmission] = field(default_factory=list)
    enrollments: list[LMSEnrollment] = field(default_factory=list)
    materials: list[LMSCourseMaterial] = field(default_factory=list)


class LMSAdapter(ABC):
    """Abstract interface for LMS platform integration.

    Implementations: CanvasAdapter, MoodleAdapter

    Design principle: auto-pull everything. Teacher does zero manual upload.
    """

    @abstractmethod
    async def get_course(self, course_id: str) -> LMSCourse:
        """Get course details including syllabus."""
        ...

    @abstractmethod
    async def get_assignments(self, course_id: str) -> list[LMSAssignment]:
        """Get all assignments for a course."""
        ...

    @abstractmethod
    async def get_submissions(
        self, course_id: str, assignment_id: str | None = None
    ) -> list[LMSSubmission]:
        """Get student submissions/grades."""
        ...

    @abstractmethod
    async def get_enrollments(self, course_id: str) -> list[LMSEnrollment]:
        """Get student roster for a course."""
        ...

    @abstractmethod
    async def get_course_materials(self, course_id: str) -> list[LMSCourseMaterial]:
        """Get all course materials (files, modules, pages, etc)."""
        ...

    @abstractmethod
    async def get_user_courses(self, user_id: str) -> list[LMSCourse]:
        """Get all courses a specific user is enrolled in."""
        ...

    async def get_grade_items(self, course_id: str) -> list[dict[str, Any]]:
        """Get gradebook columns (assignments/grade items) for a course.

        Returns [{"id": str, "name": str, "category": str, "grade_max": float}].
        """
        raise NotImplementedError("This LMS adapter does not support grade items")

    async def save_grade(
        self,
        course_id: str,
        assignment_id: str,
        student_id: str,
        grade: float,
        feedback: str | None = None,
    ) -> dict[str, Any]:
        """Write a single grade to the LMS gradebook.

        Returns {"success": bool}.
        """
        raise NotImplementedError("This LMS adapter does not support grade writing")

    async def post_announcement(self, course_id: str, title: str, message: str) -> dict[str, Any]:
        """Post an announcement to the LMS course.

        Returns {"id": str, "url": str}.
        """
        raise NotImplementedError("This LMS adapter does not support announcements")

    async def full_sync(self, course_id: str) -> LMSFullSync:
        """Pull everything for a course in one call.

        This is called on first LTI launch to fully populate the course.
        """
        course = await self.get_course(course_id)
        assignments = await self.get_assignments(course_id)
        submissions = await self.get_submissions(course_id)
        enrollments = await self.get_enrollments(course_id)
        materials = await self.get_course_materials(course_id)
        return LMSFullSync(
            course=course,
            assignments=assignments,
            submissions=submissions,
            enrollments=enrollments,
            materials=materials,
        )
