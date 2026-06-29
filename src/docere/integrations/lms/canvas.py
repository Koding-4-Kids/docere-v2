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

import asyncio
import hashlib
import io
from collections.abc import Mapping
from typing import Any

import httpx
import structlog

from docere.config import settings
from docere.integrations.lms.base import (
    LMSAdapter,
    LMSAssignment,
    LMSCourse,
    LMSCourseMaterial,
    LMSEnrollment,
    LMSSubmission,
)

logger = structlog.get_logger()

MAX_PDF_SIZE = 20 * 1024 * 1024  # 20 MB — match Moodle adapter limit

# Canvas enrollment type → normalized role
ROLE_MAP = {
    "StudentEnrollment": "student",
    "TeacherEnrollment": "teacher",
    "TaEnrollment": "ta",
}


class CanvasAdapter(LMSAdapter):
    """Canvas LMS integration via REST API."""

    def __init__(self, base_url: str | None = None, api_token: str | None = None):
        self.base_url = (base_url or settings.canvas_base_url).rstrip("/")
        self.api_token = api_token or settings.canvas_api_token
        self.headers = {"Authorization": f"Bearer {self.api_token}"}
        # Canvas rate limit: 25-token bucket, 5/sec refill. Cap concurrency at 5.
        self._semaphore = asyncio.Semaphore(5)

    async def _get(
        self,
        path: str,
        params: Mapping[str, str | list[str]] | None = None,
    ) -> object:
        """Make authenticated GET request to Canvas API."""
        async with self._semaphore:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/api/v1{path}",
                    headers=self.headers,
                    params=params,
                )
                response.raise_for_status()
                return response.json()

    async def _get_paginated(
        self,
        path: str,
        params: Mapping[str, str | list[str]] | None = None,
    ) -> list[object]:
        """Make paginated GET request, following Link headers."""
        results: list[object] = []
        url = f"{self.base_url}/api/v1{path}"
        async with httpx.AsyncClient() as client:
            while url:
                async with self._semaphore:
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

    async def get_grade_items(self, course_id: str) -> list[dict[str, Any]]:
        """Get assignment groups + assignments from Canvas.

        Returns flattened list of assignments with their group as category.
        """
        data = await self._get_paginated(
            f"/courses/{course_id}/assignment_groups",
            {"include[]": "assignments"},
        )
        items: list[dict[str, Any]] = []
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
    ) -> dict[str, Any]:
        """Write a grade to Canvas via submission update."""
        body: dict[str, Any] = {"submission": {"posted_grade": str(grade)}}
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

    async def post_announcement(self, course_id: str, title: str, message: str) -> dict[str, Any]:
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
        """Get course details including syllabus body and term."""
        data = await self._get(
            f"/courses/{course_id}",
            {"include[]": ["syllabus_body", "term"]},
        )
        assert isinstance(data, dict)
        return LMSCourse(
            external_id=str(data["id"]),
            name=data.get("name", ""),
            course_code=data.get("course_code", ""),
            syllabus_body=data.get("syllabus_body"),
            term=data.get("term", {}).get("name") if isinstance(data.get("term"), dict) else None,
        )

    async def get_assignments(self, course_id: str) -> list[LMSAssignment]:
        """Get all assignments for a course, ordered by due date."""
        data = await self._get_paginated(
            f"/courses/{course_id}/assignments",
            {"include[]": ["submission"], "order_by": "due_at"},
        )
        return [
            LMSAssignment(
                external_id=str(a["id"]),
                title=a.get("name", ""),
                description=a.get("description"),
                due_at=a.get("due_at"),
                points_possible=a.get("points_possible"),
                assignment_type=(a["submission_types"][0] if a.get("submission_types") else None),
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
        data = await self._get_paginated(path)
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
        """Get course enrollments (students, teachers, TAs) with emails.

        Two-phase fetch:
        1. List enrollments — returns user_id, type, role, and a minimal nested
           user object (id/name/short_name only — no email).
        2. For each unique user_id, fetch the user profile to get primary_email.
           Profile calls run concurrently and are throttled by the semaphore.

        Uses the `type` field (API-stable: StudentEnrollment, TeacherEnrollment,
        TaEnrollment, DesignerEnrollment, ObserverEnrollment) rather than `role`
        because admins can override `role` with custom role names.
        """
        data = await self._get_paginated(f"/courses/{course_id}/enrollments")
        enrollments_raw = [e for e in data if isinstance(e, dict)]

        # Dedup user IDs — the same user may have multiple enrollment rows
        # (e.g. concurrent student + observer enrollments) and we only want
        # to hit the profile endpoint once per user.
        unique_user_ids = list({str(e["user_id"]) for e in enrollments_raw})
        emails = await asyncio.gather(*[self._fetch_user_email(uid) for uid in unique_user_ids])
        email_by_user_id = dict(zip(unique_user_ids, emails, strict=True))

        return [
            LMSEnrollment(
                user_id=str(e["user_id"]),
                course_id=course_id,
                role=ROLE_MAP.get(e.get("type", ""), "student"),
                name=e.get("user", {}).get("name", ""),
                email=email_by_user_id.get(str(e["user_id"])),
            )
            for e in enrollments_raw
        ]

    async def _fetch_user_email(self, user_id: str) -> str | None:
        """Fetch a user's primary email via the Canvas Profile endpoint.

        Canvas endpoint: GET /api/v1/users/:id/profile → returns
        { id, name, primary_email, time_zone, ... }.
        Returns None on failure (graceful degradation — caller still creates
        the enrollment row, just without email).
        """
        try:
            data = await self._get(f"/users/{user_id}/profile")
        except Exception:
            logger.warning("Failed to fetch Canvas user profile", user_id=user_id)
            return None

        if not isinstance(data, dict):
            return None

        return data.get("primary_email") or None

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
        """Get all course materials by walking the Modules tree.

        For each module item:
        - File: fetch file metadata, download PDF if applicable, extract text via pypdf
        - Page: fetch HTML body via the Pages API
        - Assignment / Discussion / ExternalUrl / ExternalTool / Quiz: metadata only
        - SubHeader: skipped (visual divider, no content)

        Files are deduplicated by Canvas file ID — the same file linked in multiple
        modules produces a single material record. SHA256 content_hash on extracted
        content enables incremental sync to skip re-embedding unchanged materials.
        """
        materials: list[LMSCourseMaterial] = []
        seen_file_ids: set[str] = set()

        modules = await self._get_paginated(
            f"/courses/{course_id}/modules",
            {"include[]": "items"},
        )

        for module in modules:
            if not isinstance(module, dict):
                continue
            for item in module.get("items", []):
                if not isinstance(item, dict):
                    continue

                item_type = item.get("type", "")
                title = item.get("title", "")

                if item_type == "SubHeader":
                    # Visual divider only — no content to ingest
                    continue

                if item_type == "File":
                    file_id = str(item.get("content_id", ""))
                    if not file_id or file_id in seen_file_ids:
                        continue
                    seen_file_ids.add(file_id)
                    content, content_hash = await self._extract_file_content(course_id, file_id)
                    materials.append(
                        LMSCourseMaterial(
                            external_id=file_id,
                            title=title,
                            material_type="file",
                            content=content,
                            content_hash=content_hash,
                            url=item.get("html_url"),
                        )
                    )

                elif item_type == "Page":
                    page_url = item.get("page_url", "")
                    if not page_url:
                        continue
                    content, content_hash = await self._fetch_page_content(course_id, page_url)
                    materials.append(
                        LMSCourseMaterial(
                            external_id=page_url,
                            title=title,
                            material_type="page",
                            content=content,
                            content_hash=content_hash,
                            url=item.get("html_url"),
                        )
                    )

                else:
                    # Assignment, Discussion, ExternalUrl, ExternalTool, Quiz — metadata only
                    materials.append(
                        LMSCourseMaterial(
                            external_id=str(item.get("id", "")),
                            title=title,
                            material_type=item_type.lower(),
                            url=item.get("html_url"),
                        )
                    )

        return materials

    async def get_effective_due_dates(self, course_id: str) -> dict[str, Any]:
        """Get per-student effective due dates for all assignments in a course.

        Canvas endpoint: GET /api/v1/courses/:id/effective_due_dates
        Returns mapping of { assignment_id: { student_id: { due_at, grading_period_id } } }.

        Useful for the tutoring agent when due dates are overridden per-student
        (extensions, accommodations). Not part of the abstract LMSAdapter
        interface — Canvas-specific extension.
        """
        data = await self._get(f"/courses/{course_id}/effective_due_dates")
        assert isinstance(data, dict)
        return data

    async def _extract_file_content(
        self, course_id: str, file_id: str
    ) -> tuple[str | None, str | None]:
        """Fetch Canvas file metadata; if it's a PDF, download and extract text.

        Returns (content, content_hash). Both None when the file is not a PDF
        or extraction fails (graceful degradation — caller still saves the
        material row, just without content/embedding).
        """
        try:
            file_data = await self._get(f"/courses/{course_id}/files/{file_id}")
        except Exception:
            logger.warning("Failed to fetch Canvas file metadata", file_id=file_id)
            return None, None

        if not isinstance(file_data, dict):
            return None, None

        # Canvas Files API uses "content-type" (hyphenated, matching the HTTP header).
        # Some implementations also expose "content_type" — check both.
        content_type = file_data.get("content-type") or file_data.get("content_type", "")
        download_url = file_data.get("url", "")

        if content_type != "application/pdf" or not download_url:
            return None, None

        try:
            content = await self._download_and_extract_pdf(download_url)
        except Exception:
            logger.warning("Canvas PDF extraction failed", file_id=file_id, url=download_url)
            return None, None

        if not content:
            return None, None

        content_hash = hashlib.sha256(content.encode()).hexdigest()
        return content, content_hash

    async def _fetch_page_content(
        self, course_id: str, page_url: str
    ) -> tuple[str | None, str | None]:
        """Fetch a Canvas page's HTML body via the Pages API.

        Canvas endpoint: GET /api/v1/courses/:id/pages/:url_or_id → returns
        page object whose `body` field contains the HTML content.
        Returns (body_html, content_hash). Both None on failure.
        """
        try:
            page_data = await self._get(f"/courses/{course_id}/pages/{page_url}")
        except Exception:
            logger.warning("Failed to fetch Canvas page", page_url=page_url)
            return None, None

        if not isinstance(page_data, dict):
            return None, None

        body = page_data.get("body") or ""
        if not body:
            return None, None

        content_hash = hashlib.sha256(body.encode()).hexdigest()
        return body, content_hash

    async def _download_and_extract_pdf(self, url: str) -> str | None:
        """Download a Canvas-hosted PDF and extract its text.

        Uses Authorization: Bearer header for auth (Canvas's standard, unlike
        Moodle which appends ?token=). Streams the response and enforces a
        20 MB size limit. Returns None on failure or if no extractable text.
        """
        from pypdf import PdfReader

        async with httpx.AsyncClient() as client:
            async with client.stream(
                "GET", url, headers=self.headers, follow_redirects=True
            ) as response:
                response.raise_for_status()

                # Reject oversize files before downloading (when possible)
                content_length = response.headers.get("content-length")
                if content_length and int(content_length) > MAX_PDF_SIZE:
                    logger.warning("Canvas PDF too large, skipping", url=url, size=content_length)
                    return None

                # Stream the PDF with size enforcement
                chunks: list[bytes] = []
                total_size = 0
                async for chunk in response.aiter_bytes(chunk_size=8192):
                    total_size += len(chunk)
                    if total_size > MAX_PDF_SIZE:
                        logger.warning("Canvas PDF exceeded size limit", url=url)
                        return None
                    chunks.append(chunk)

        pdf_bytes = b"".join(chunks)
        if not pdf_bytes:
            return None

        try:
            reader = PdfReader(io.BytesIO(pdf_bytes))
            text_parts: list[str] = []
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
            return "\n".join(text_parts) if text_parts else None
        except Exception:
            logger.warning("Failed to parse Canvas PDF", url=url)
            return None
