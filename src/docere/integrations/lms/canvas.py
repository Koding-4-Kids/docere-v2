"""Canvas LMS adapter.

Uses Canvas REST API to auto-pull all course data.
Zero manual upload required from teachers.

Key endpoints:
- GET /api/v1/courses/:id?include[]=syllabus_body - syllabus
- GET /api/v1/courses/:id/assignments - all assignments + rubrics
- GET /api/v1/courses/:id/files - lecture files, attachments
- GET /api/v1/courses/:id/modules?include[]=items - course structure
- GET /api/v1/courses/:id/enrollments - student roster
- GET /api/v1/courses/:id/students/submissions - grades + submissions
- GET /api/v1/courses/:id/discussion_topics - discussions
- GET /api/v1/courses/:id/quizzes - quizzes
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


class CanvasAdapter(LMSAdapter):
    """Canvas LMS integration via REST API."""

    def __init__(self, base_url: str | None = None, api_token: str | None = None):
        self.base_url = (base_url or settings.canvas_base_url).rstrip("/")
        self.api_token = api_token or settings.canvas_api_token
        self.headers = {"Authorization": f"Bearer {self.api_token}"}

    async def _get(self, path: str, params: dict[str, str] | None = None) -> object:
        """Make authenticated GET request to Canvas API."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1{path}",
                headers=self.headers,
                params=params or {},
            )
            response.raise_for_status()
            return response.json()

    async def _get_paginated(self, path: str, params: dict[str, str] | None = None) -> list[object]:
        """Make paginated GET request, following Link headers."""
        results: list[object] = []
        url = f"{self.base_url}/api/v1{path}"
        async with httpx.AsyncClient() as client:
            while url:
                response = await client.get(url, headers=self.headers, params=params)
                response.raise_for_status()
                results.extend(response.json())
                # Follow pagination
                link_header = response.headers.get("Link", "")
                url = ""
                for link in link_header.split(","):
                    if 'rel="next"' in link:
                        url = link.split(";")[0].strip().strip("<>")
                params = None  # Only use params on first request
        return results

    async def get_grade_items(self, course_id: str) -> list[dict]:
        """Get assignment groups + assignments from Canvas.

        Returns flattened list of assignments with their group as category.
        """
        data = await self._get_paginated(
            f"/courses/{course_id}/assignment_groups",
            {"include[]": "assignments"},
        )
        items: list[dict] = []
        for group in data:
            if not isinstance(group, dict):
                continue
            category = group.get("name", "Uncategorized")
            for a in group.get("assignments", []):
                if isinstance(a, dict):
                    items.append(
                        {
                            "id": str(a["id"]),
                            "name": a.get("name", ""),
                            "category": category,
                            "grade_max": float(a.get("points_possible", 100) or 100),
                        }
                    )
        return items

    async def save_grade(
        self,
        course_id: str,
        assignment_id: str,
        student_id: str,
        grade: float,
        feedback: str | None = None,
    ) -> dict:
        """Write a grade to Canvas via submission update."""
        body: dict = {"submission": {"posted_grade": str(grade)}}
        if feedback:
            body["comment"] = {"text_comment": feedback}

        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"{self.base_url}/api/v1/courses/{course_id}/assignments/{assignment_id}/submissions/{student_id}",
                headers=self.headers,
                json=body,
            )
            response.raise_for_status()
        return {"success": True}

    async def post_announcement(self, course_id: str, title: str, message: str) -> dict:
        """Post announcement via Canvas discussion topics API."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/courses/{course_id}/discussion_topics",
                headers=self.headers,
                json={
                    "title": title,
                    "message": message,
                    "is_announcement": True,
                    "published": True,
                },
            )
            response.raise_for_status()
            data = response.json()

        return {
            "id": str(data.get("id", "")),
            "url": data.get("html_url", ""),
        }

    async def get_course(self, course_id: str) -> LMSCourse:
        """Get course details including syllabus body."""
        data = await self._get(f"/courses/{course_id}", {"include[]": "syllabus_body"})
        assert isinstance(data, dict)
        return LMSCourse(
            external_id=str(data["id"]),
            name=data.get("name", ""),
            course_code=data.get("course_code", ""),
            syllabus_body=data.get("syllabus_body"),
            term=data.get("term", {}).get("name") if isinstance(data.get("term"), dict) else None,
        )

    async def get_assignments(self, course_id: str) -> list[LMSAssignment]:
        """Get all assignments for a course."""
        data = await self._get_paginated(f"/courses/{course_id}/assignments")
        return [
            LMSAssignment(
                external_id=str(a["id"]),
                title=a.get("name", ""),
                description=a.get("description"),
                due_at=a.get("due_at"),
                points_possible=a.get("points_possible"),
                assignment_type=a.get("submission_types", [None])[0]
                if a.get("submission_types")
                else None,
            )
            for a in data
            if isinstance(a, dict)
        ]

    async def get_submissions(
        self, course_id: str, assignment_id: str | None = None
    ) -> list[LMSSubmission]:
        """Get student submissions/grades."""
        if assignment_id:
            path = f"/courses/{course_id}/assignments/{assignment_id}/submissions"
        else:
            path = f"/courses/{course_id}/students/submissions"
        data = await self._get_paginated(path, {"include[]": "assignment"})
        return [
            LMSSubmission(
                external_id=str(s["id"]),
                assignment_id=str(s.get("assignment_id", "")),
                student_id=str(s.get("user_id", "")),
                score=s.get("score"),
                grade=s.get("grade"),
                submitted_at=s.get("submitted_at"),
                graded_at=s.get("graded_at"),
                workflow_state=s.get("workflow_state", "submitted"),
            )
            for s in data
            if isinstance(s, dict)
        ]

    async def get_enrollments(self, course_id: str) -> list[LMSEnrollment]:
        """Get student roster for a course."""
        data = await self._get_paginated(
            f"/courses/{course_id}/enrollments",
            {"type[]": "StudentEnrollment"},
        )
        return [
            LMSEnrollment(
                user_id=str(e["user_id"]),
                course_id=course_id,
                role="student",
                name=e.get("user", {}).get("name", ""),
                email=e.get("user", {}).get("email"),
            )
            for e in data
            if isinstance(e, dict)
        ]

    async def get_user_courses(self, user_id: str) -> list[LMSCourse]:
        """Get all courses a user is enrolled in via Canvas."""
        data = await self._get_paginated(
            f"/users/{user_id}/courses",
            {"enrollment_state": "active"},
        )
        return [
            LMSCourse(
                external_id=str(c["id"]),
                name=c.get("name", ""),
                course_code=c.get("course_code", ""),
            )
            for c in data
            if isinstance(c, dict)
        ]

    async def get_course_materials(self, course_id: str) -> list[LMSCourseMaterial]:
        """Get all course materials: modules, files, pages."""
        materials: list[LMSCourseMaterial] = []

        # Get modules with items
        modules = await self._get_paginated(
            f"/courses/{course_id}/modules",
            {"include[]": "items"},
        )
        for mod in modules:
            if not isinstance(mod, dict):
                continue
            for item in mod.get("items", []):
                if isinstance(item, dict):
                    materials.append(
                        LMSCourseMaterial(
                            external_id=str(item.get("id", "")),
                            title=item.get("title", ""),
                            material_type=item.get("type", "module_item").lower(),
                            url=item.get("html_url"),
                        )
                    )

        # Get files
        files = await self._get_paginated(f"/courses/{course_id}/files")
        for f in files:
            if isinstance(f, dict):
                materials.append(
                    LMSCourseMaterial(
                        external_id=str(f.get("id", "")),
                        title=f.get("display_name", ""),
                        material_type="file",
                        url=f.get("url"),
                    )
                )

        return materials
