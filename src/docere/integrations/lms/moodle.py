"""Moodle LMS adapter.

Uses Moodle Web Services API to auto-pull all course data.

Key functions:
- core_course_get_contents - full course structure with resources
- mod_assign_get_assignments - assignments
- core_enrol_get_enrolled_users - student roster
- gradereport_user_get_grades_table - grades
"""

import httpx

from docere.config import settings
from docere.integrations.lms.base import (
    LMSAdapter,
    LMSAssignment,
    LMSCourse,
    LMSCourseMaterial,
    LMSEnrollment,
    LMSSubmission,
)


class MoodleAdapter(LMSAdapter):
    """Moodle LMS integration via Web Services API."""

    def __init__(self, base_url: str | None = None, api_token: str | None = None):
        self.base_url = (base_url or settings.moodle_base_url).rstrip("/")
        self.api_token = api_token or settings.moodle_api_token

    async def _call(self, function: str, params: dict[str, object] | None = None) -> object:
        """Make a Moodle Web Services API call."""
        request_params: dict[str, object] = {
            "wstoken": self.api_token,
            "wsfunction": function,
            "moodlewsrestformat": "json",
            **(params or {}),
        }
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/webservice/rest/server.php",
                params=request_params,
            )
            response.raise_for_status()
            return response.json()

    async def get_course(self, course_id: str) -> LMSCourse:
        """Get course details."""
        data = await self._call(
            "core_course_get_courses",
            {"options[ids][0]": course_id},
        )
        assert isinstance(data, list) and len(data) > 0
        course = data[0]
        return LMSCourse(
            external_id=str(course["id"]),
            name=course.get("fullname", ""),
            course_code=course.get("shortname", ""),
            syllabus_body=course.get("summary"),
        )

    async def get_assignments(self, course_id: str) -> list[LMSAssignment]:
        """Get all assignments for a course."""
        data = await self._call(
            "mod_assign_get_assignments",
            {"courseids[0]": course_id},
        )
        assert isinstance(data, dict)
        assignments = []
        for course_data in data.get("courses", []):
            for a in course_data.get("assignments", []):
                assignments.append(
                    LMSAssignment(
                        external_id=str(a["id"]),
                        title=a.get("name", ""),
                        description=a.get("intro"),
                        due_at=str(a.get("duedate")) if a.get("duedate") else None,
                        points_possible=a.get("grade"),
                    )
                )
        return assignments

    async def get_submissions(
        self, course_id: str, assignment_id: str | None = None
    ) -> list[LMSSubmission]:
        """Get student grades via gradebook."""
        data = await self._call(
            "gradereport_user_get_grades_table",
            {"courseid": course_id},
        )
        assert isinstance(data, dict)
        submissions = []
        for table in data.get("tables", []):
            user_id = str(table.get("userid", ""))
            for row in table.get("tabledata", []):
                if isinstance(row, dict) and row.get("itemname"):
                    submissions.append(
                        LMSSubmission(
                            external_id=f"{user_id}_{row.get('itemname', {}).get('id', '')}",
                            assignment_id=str(row.get("itemname", {}).get("id", "")),
                            student_id=user_id,
                            grade=row.get("grade", {}).get("content"),
                        )
                    )
        return submissions

    async def get_enrollments(self, course_id: str) -> list[LMSEnrollment]:
        """Get student roster for a course."""
        data = await self._call(
            "core_enrol_get_enrolled_users",
            {"courseid": course_id},
        )
        assert isinstance(data, list)
        return [
            LMSEnrollment(
                user_id=str(u["id"]),
                course_id=course_id,
                role="student" if any(
                    r.get("shortname") == "student" for r in u.get("roles", [])
                ) else "teacher",
                name=u.get("fullname", ""),
                email=u.get("email"),
            )
            for u in data
            if isinstance(u, dict)
        ]

    async def get_course_materials(self, course_id: str) -> list[LMSCourseMaterial]:
        """Get all course materials via core_course_get_contents."""
        data = await self._call(
            "core_course_get_contents",
            {"courseid": course_id},
        )
        assert isinstance(data, list)
        materials = []
        for section in data:
            if not isinstance(section, dict):
                continue
            for module in section.get("modules", []):
                if isinstance(module, dict):
                    materials.append(
                        LMSCourseMaterial(
                            external_id=str(module.get("id", "")),
                            title=module.get("name", ""),
                            material_type=module.get("modname", "resource"),
                            content=module.get("description"),
                            url=module.get("url"),
                        )
                    )
        return materials
