"""LMS sync service: auto-pulls everything from Canvas/Moodle into the database.

Zero manual upload required from teachers. On first LTI launch:
1. Pull course details + syllabus
2. Pull all assignments + rubrics
3. Pull student roster
4. Pull all grades/submissions
5. Pull course files + module structure

Ongoing: sync every 2 hours + webhook triggers.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from docere.integrations.lms.base import LMSAdapter, LMSFullSync
from docere.models.course import Assignment, Course, CourseMaterial, Enrollment, Submission
from docere.models.user import User

logger = structlog.get_logger()


@dataclass
class GradeChange:
    """Detected grade change from LMS sync."""

    student_id: uuid.UUID
    course_id: uuid.UUID
    assignment_id: uuid.UUID
    assignment_title: str
    score: float
    max_score: float
    previous_score: float | None


class LMSSyncService:
    """Syncs LMS data into the Docere database."""

    def __init__(self, db: AsyncSession, lms_adapter: LMSAdapter):
        self.db = db
        self.lms = lms_adapter

    async def full_sync(self, external_course_id: str, lms_platform: str) -> Course:
        """Full course sync on first connect. Auto-pulls everything.

        This is called on first LTI launch. Teacher does nothing.
        """
        logger.info(
            "Starting full LMS sync",
            course_id=external_course_id,
            platform=lms_platform,
        )

        sync_data = await self.lms.full_sync(external_course_id)

        # Upsert course
        course = await self._upsert_course(sync_data, lms_platform)

        # Sync all data in parallel-ish order
        await self._sync_enrollments(course, sync_data, lms_platform)
        await self._sync_assignments(course, sync_data)
        await self._sync_submissions(course, sync_data)
        await self._sync_materials(course, sync_data)

        # Update last synced timestamp
        course.last_synced_at = datetime.now(timezone.utc)
        await self.db.commit()

        logger.info(
            "Full LMS sync complete",
            course_id=str(course.id),
            assignments=len(sync_data.assignments),
            enrollments=len(sync_data.enrollments),
            submissions=len(sync_data.submissions),
            materials=len(sync_data.materials),
        )
        return course

    async def incremental_sync(
        self, course_id: uuid.UUID
    ) -> tuple[dict[str, int], list[GradeChange]]:
        """Incremental sync: pull latest grades, submissions, new assignments, and materials.

        Called every 2 hours by background task or on webhook trigger.

        Returns:
            (summary_dict, list_of_grade_changes)
        """
        course = await self.db.get(Course, course_id)
        if not course or not course.external_lms_id:
            raise ValueError(f"Course {course_id} not found or not linked to LMS")

        # Pull latest data
        assignments = await self.lms.get_assignments(course.external_lms_id)
        submissions = await self.lms.get_submissions(course.external_lms_id)
        materials = await self.lms.get_course_materials(course.external_lms_id)

        sync_data = LMSFullSync(
            course=await self.lms.get_course(course.external_lms_id),
            assignments=assignments,
            submissions=submissions,
            enrollments=[],
            materials=materials,
        )

        new_assignments = await self._sync_assignments(course, sync_data)
        new_submissions, grade_changes = await self._sync_submissions(course, sync_data)
        new_materials, updated_materials = await self._sync_materials(course, sync_data)

        course.last_synced_at = datetime.now(timezone.utc)
        await self.db.commit()

        return (
            {
                "new_assignments": new_assignments,
                "updated_submissions": new_submissions,
                "new_materials": new_materials,
                "updated_materials": updated_materials,
            },
            grade_changes,
        )

    async def _upsert_course(self, sync_data: LMSFullSync, lms_platform: str) -> Course:
        """Create or update a course from LMS data."""
        result = await self.db.execute(
            select(Course).where(
                Course.external_lms_id == sync_data.course.external_id,
                Course.lms_platform == lms_platform,
            )
        )
        course = result.scalar_one_or_none()

        if course:
            course.name = sync_data.course.name
            course.course_code = sync_data.course.course_code
            course.syllabus_text = sync_data.course.syllabus_body
            course.term = sync_data.course.term
        else:
            course = Course(
                external_lms_id=sync_data.course.external_id,
                lms_platform=lms_platform,
                name=sync_data.course.name,
                course_code=sync_data.course.course_code,
                syllabus_text=sync_data.course.syllabus_body,
                term=sync_data.course.term,
            )
            self.db.add(course)
            await self.db.flush()

        return course

    async def _sync_enrollments(
        self, course: Course, sync_data: LMSFullSync, lms_platform: str
    ) -> int:
        """Sync student roster from LMS."""
        count = 0
        for lms_enrollment in sync_data.enrollments:
            # Find or create user
            result = await self.db.execute(
                select(User).where(
                    User.external_lms_id == lms_enrollment.user_id,
                    User.lms_platform == lms_platform,
                )
            )
            user = result.scalar_one_or_none()

            if not user:
                user = User(
                    external_lms_id=lms_enrollment.user_id,
                    lms_platform=lms_platform,
                    name=lms_enrollment.name,
                    email=lms_enrollment.email,
                    role=lms_enrollment.role if lms_enrollment.role != "teacher" else "instructor",
                )
                self.db.add(user)
                await self.db.flush()

            # Check if enrollment exists
            result = await self.db.execute(
                select(Enrollment).where(
                    Enrollment.user_id == user.id,
                    Enrollment.course_id == course.id,
                )
            )
            if not result.scalar_one_or_none():
                self.db.add(
                    Enrollment(
                        user_id=user.id,
                        course_id=course.id,
                        lms_role=lms_enrollment.role,
                    )
                )
                count += 1

        await self.db.flush()
        return count

    async def _sync_assignments(self, course: Course, sync_data: LMSFullSync) -> int:
        """Sync assignments from LMS."""
        count = 0
        for lms_assignment in sync_data.assignments:
            result = await self.db.execute(
                select(Assignment).where(
                    Assignment.course_id == course.id,
                    Assignment.external_lms_id == lms_assignment.external_id,
                )
            )
            assignment = result.scalar_one_or_none()

            if assignment:
                assignment.title = lms_assignment.title
                assignment.description = lms_assignment.description
                assignment.points_possible = lms_assignment.points_possible
                assignment.assignment_type = lms_assignment.assignment_type
            else:
                self.db.add(
                    Assignment(
                        course_id=course.id,
                        external_lms_id=lms_assignment.external_id,
                        title=lms_assignment.title,
                        description=lms_assignment.description,
                        points_possible=lms_assignment.points_possible,
                        assignment_type=lms_assignment.assignment_type,
                    )
                )
                count += 1

        await self.db.flush()
        return count

    async def _sync_submissions(
        self, course: Course, sync_data: LMSFullSync
    ) -> tuple[int, list[GradeChange]]:
        """Sync student submissions/grades from LMS.

        Returns:
            (count_updated, list_of_grade_changes)
        """
        count = 0
        grade_changes: list[GradeChange] = []

        # Build lookup maps for assignments and users
        assignment_map: dict[str, uuid.UUID] = {}
        assignment_titles: dict[str, str] = {}
        assignment_points: dict[str, float] = {}
        result = await self.db.execute(
            select(Assignment.external_lms_id, Assignment.id, Assignment.title, Assignment.points_possible)
            .where(Assignment.course_id == course.id)
        )
        for ext_id, db_id, title, points in result.all():
            if ext_id:
                assignment_map[ext_id] = db_id
                assignment_titles[ext_id] = title
                assignment_points[ext_id] = points or 0

        user_map: dict[str, uuid.UUID] = {}
        result = await self.db.execute(
            select(User.external_lms_id, User.id).where(
                User.lms_platform == course.lms_platform
            )
        )
        for ext_id, db_id in result.all():
            if ext_id:
                user_map[ext_id] = db_id

        for lms_sub in sync_data.submissions:
            assignment_id = assignment_map.get(lms_sub.assignment_id)
            student_id = user_map.get(lms_sub.student_id)

            if not assignment_id or not student_id:
                continue

            result = await self.db.execute(
                select(Submission).where(
                    Submission.assignment_id == assignment_id,
                    Submission.student_id == student_id,
                )
            )
            submission = result.scalar_one_or_none()

            if submission:
                previous_score = submission.score
                submission.score = lms_sub.score
                submission.grade = lms_sub.grade
                submission.workflow_state = lms_sub.workflow_state
                submission.synced_at = datetime.now(timezone.utc)

                # Detect grade change
                if lms_sub.score is not None and lms_sub.score != previous_score:
                    grade_changes.append(GradeChange(
                        student_id=student_id,
                        course_id=course.id,
                        assignment_id=assignment_id,
                        assignment_title=assignment_titles.get(lms_sub.assignment_id, ""),
                        score=lms_sub.score,
                        max_score=assignment_points.get(lms_sub.assignment_id, 0),
                        previous_score=previous_score,
                    ))
            else:
                self.db.add(
                    Submission(
                        assignment_id=assignment_id,
                        student_id=student_id,
                        external_lms_id=lms_sub.external_id,
                        score=lms_sub.score,
                        grade=lms_sub.grade,
                        workflow_state=lms_sub.workflow_state,
                    )
                )
                # New submission with a grade is also a "change"
                if lms_sub.score is not None:
                    grade_changes.append(GradeChange(
                        student_id=student_id,
                        course_id=course.id,
                        assignment_id=assignment_id,
                        assignment_title=assignment_titles.get(lms_sub.assignment_id, ""),
                        score=lms_sub.score,
                        max_score=assignment_points.get(lms_sub.assignment_id, 0),
                        previous_score=None,
                    ))
            count += 1

        await self.db.flush()
        return count, grade_changes

    async def _sync_materials(
        self, course: Course, sync_data: LMSFullSync
    ) -> tuple[int, int]:
        """Sync course materials (files, modules, pages) from LMS.

        Uses external_lms_id for stable matching. Compares content_hash
        for change detection. Clears embedding_id when content changes
        so re-embedding is triggered.

        Returns:
            (new_count, updated_count)
        """
        new_count = 0
        updated_count = 0

        for lms_material in sync_data.materials:
            # Look up by stable external_lms_id
            result = await self.db.execute(
                select(CourseMaterial).where(
                    CourseMaterial.course_id == course.id,
                    CourseMaterial.external_lms_id == lms_material.external_id,
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                # Check for content changes via hash
                if (
                    lms_material.content_hash
                    and existing.content_hash != lms_material.content_hash
                ):
                    existing.title = lms_material.title
                    existing.content = lms_material.content
                    existing.content_hash = lms_material.content_hash
                    existing.source_url = lms_material.url
                    existing.material_type = lms_material.material_type
                    # Clear embedding so re-embedding is triggered
                    existing.embedding_id = None
                    updated_count += 1
            else:
                self.db.add(
                    CourseMaterial(
                        course_id=course.id,
                        external_lms_id=lms_material.external_id,
                        material_type=lms_material.material_type,
                        title=lms_material.title,
                        content=lms_material.content,
                        content_hash=lms_material.content_hash,
                        source_url=lms_material.url,
                    )
                )
                new_count += 1

        await self.db.flush()
        return new_count, updated_count
