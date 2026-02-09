"""Moodle LMS adapter.

Uses Moodle Web Services API to auto-pull all course data.

Key functions:
- core_course_get_contents - full course structure with resources
- mod_assign_get_assignments - assignments
- core_enrol_get_enrolled_users - student roster
- gradereport_user_get_grades_table - grades
- mod_page_get_pages_by_courses - page HTML content
"""

import hashlib
import io

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

MAX_PDF_SIZE = 20 * 1024 * 1024  # 20 MB


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
        """Get all course materials via core_course_get_contents + page content.

        Reads the contents[] array from each module to find file download URLs,
        downloads and extracts PDF text, fetches page HTML content, and computes
        content_hash for change detection.
        """
        data = await self._call(
            "core_course_get_contents",
            {"courseid": course_id},
        )
        assert isinstance(data, list)

        # Fetch page content in bulk
        page_content_map = await self._get_page_contents(course_id)

        materials = []
        for section in data:
            if not isinstance(section, dict):
                continue
            for module in section.get("modules", []):
                if not isinstance(module, dict):
                    continue

                module_id = str(module.get("id", ""))
                modname = module.get("modname", "resource")
                title = module.get("name", "")

                # Extract file download URLs from contents array
                file_urls: list[str] = []
                for content_item in module.get("contents", []):
                    if isinstance(content_item, dict):
                        file_url = content_item.get("fileurl")
                        if file_url:
                            file_urls.append(file_url)

                # Determine content: page HTML, PDF text, or module description
                content = module.get("description")

                if modname == "page" and module_id in page_content_map:
                    content = page_content_map[module_id]
                elif file_urls:
                    pdf_text = await self._extract_pdf_text(file_urls)
                    if pdf_text:
                        content = pdf_text

                # Compute content hash for change detection
                content_hash = None
                if content:
                    content_hash = hashlib.sha256(content.encode()).hexdigest()

                materials.append(
                    LMSCourseMaterial(
                        external_id=module_id,
                        title=title,
                        material_type=modname,
                        content=content,
                        url=module.get("url"),
                        file_urls=file_urls,
                        content_hash=content_hash,
                    )
                )
        return materials

    async def _get_page_contents(self, course_id: str) -> dict[str, str]:
        """Fetch HTML content for all page modules in a course.

        Returns mapping of module_id -> HTML content.
        """
        try:
            data = await self._call(
                "mod_page_get_pages_by_courses",
                {"courseids[0]": course_id},
            )
        except Exception:
            logger.warning("Failed to fetch page contents", course_id=course_id)
            return {}

        if not isinstance(data, dict):
            return {}

        pages: dict[str, str] = {}
        for page in data.get("pages", []):
            if isinstance(page, dict):
                cm_id = str(page.get("coursemodule", ""))
                html_content = page.get("content", "")
                if cm_id and html_content:
                    pages[cm_id] = html_content
        return pages

    async def _extract_pdf_text(self, file_urls: list[str]) -> str | None:
        """Download PDF files from Moodle and extract text.

        Appends ?token=WSTOKEN for Moodle file auth. Streams with size limit.
        Returns concatenated text from all PDFs, or None if no PDFs found.
        """
        all_text_parts: list[str] = []

        for url in file_urls:
            # Only attempt PDF extraction for URLs that look like PDFs
            url_lower = url.lower()
            if not url_lower.endswith(".pdf") and "pdf" not in url_lower:
                continue

            try:
                text = await self._download_and_extract_pdf(url)
                if text:
                    all_text_parts.append(text)
            except Exception:
                logger.warning("Failed to extract PDF", url=url)

        return "\n\n".join(all_text_parts) if all_text_parts else None

    async def _download_and_extract_pdf(self, url: str) -> str | None:
        """Download a single PDF from Moodle and extract its text.

        Appends ?token=WSTOKEN for Moodle file authentication.
        Enforces a 20MB size limit via streaming.
        """
        from pypdf import PdfReader

        # Append Moodle auth token
        separator = "&" if "?" in url else "?"
        auth_url = f"{url}{separator}token={self.api_token}"

        async with httpx.AsyncClient() as client:
            async with client.stream("GET", auth_url, follow_redirects=True) as response:
                response.raise_for_status()

                # Check content length if available
                content_length = response.headers.get("content-length")
                if content_length and int(content_length) > MAX_PDF_SIZE:
                    logger.warning("PDF too large, skipping", url=url, size=content_length)
                    return None

                # Stream the PDF with size limit
                chunks: list[bytes] = []
                total_size = 0
                async for chunk in response.aiter_bytes(chunk_size=8192):
                    total_size += len(chunk)
                    if total_size > MAX_PDF_SIZE:
                        logger.warning("PDF exceeded size limit during download", url=url)
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
            logger.warning("Failed to parse PDF", url=url)
            return None
