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
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from docere.integrations.lms.base import LMSAdapter, LMSFullSync
from docere.models.course import Assignment, Course, CourseMaterial, Enrollment, Submission
from docere.models.user import User

logger = structlog.get_logger()


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

    async def incremental_sync(self, course_id: uuid.UUID) -> dict[str, int]:
        """Incremental sync: pull latest grades, submissions, new assignments.

        Called every 2 hours by background task or on webhook trigger.
        """
        course = await self.db.get(Course, course_id)
        if not course or not course.external_lms_id:
            raise ValueError(f"Course {course_id} not found or not linked to LMS")

        # Pull latest data
        assignments = await self.lms.get_assignments(course.external_lms_id)
        submissions = await self.lms.get_submissions(course.external_lms_id)

        sync_data = LMSFullSync(
            course=await self.lms.get_course(course.external_lms_id),
            assignments=assignments,
            submissions=submissions,
            enrollments=[],
            materials=[],
        )

        new_assignments = await self._sync_assignments(course, sync_data)
        new_submissions = await self._sync_submissions(course, sync_data)

        course.last_synced_at = datetime.now(timezone.utc)
        await self.db.commit()

        return {"new_assignments": new_assignments, "updated_submissions": new_submissions}

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

    async def _sync_submissions(self, course: Course, sync_data: LMSFullSync) -> int:
        """Sync student submissions/grades from LMS."""
        count = 0

        # Build lookup maps for assignments and users
        assignment_map: dict[str, uuid.UUID] = {}
        result = await self.db.execute(
            select(Assignment.external_lms_id, Assignment.id).where(
                Assignment.course_id == course.id
            )
        )
        for ext_id, db_id in result.all():
            if ext_id:
                assignment_map[ext_id] = db_id

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
                submission.score = lms_sub.score
                submission.grade = lms_sub.grade
                submission.workflow_state = lms_sub.workflow_state
                submission.synced_at = datetime.now(timezone.utc)
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
            count += 1

        await self.db.flush()
        return count

    async def _sync_materials(self, course: Course, sync_data: LMSFullSync) -> int:
        """Sync course materials (files, modules, pages) from LMS."""
        count = 0
        for lms_material in sync_data.materials:
            result = await self.db.execute(
                select(CourseMaterial).where(
                    CourseMaterial.course_id == course.id,
                    CourseMaterial.title == lms_material.title,
                    CourseMaterial.material_type == lms_material.material_type,
                )
            )
            if not result.scalar_one_or_none():
                self.db.add(
                    CourseMaterial(
                        course_id=course.id,
                        material_type=lms_material.material_type,
                        title=lms_material.title,
                        content=lms_material.content,
                        source_url=lms_material.url,
                    )
                )
                count += 1

        await self.db.flush()
        return count
