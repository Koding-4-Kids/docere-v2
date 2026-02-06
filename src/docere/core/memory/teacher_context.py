"""Teacher context management: auto-pulled from LMS.

Handles ingestion and compression of course materials:
- Syllabus, assignments, rubrics (auto-pulled from Canvas/Moodle)
- Lecture files and attachments
- Module structure
- CARTRIDGES-inspired compression via synthetic Q&A distillation
"""


class TeacherContextManager:
    """Manages teacher/course context auto-pulled from LMS."""

    async def ingest_course(self, course_id: str) -> None:
        """Auto-ingest all course materials from LMS.

        Called on first LTI launch. Pulls and embeds:
        - Syllabus body
        - All assignments + rubrics
        - Course files/attachments
        - Module structure
        - Announcements, discussions, quizzes

        Teacher does nothing - everything is auto-pulled.
        """
        # TODO: Pull from LMS adapter, chunk, embed, compress
        raise NotImplementedError

    async def refresh_course(self, course_id: str) -> None:
        """Sync any new/updated materials from LMS."""
        # TODO: Diff against last sync, update changed materials
        raise NotImplementedError

    async def retrieve_relevant_context(
        self,
        course_id: str,
        query: str,
        max_tokens: int = 1500,
    ) -> str:
        """Retrieve course materials relevant to a student's query."""
        # TODO: Embed query, search Qdrant course materials collection
        raise NotImplementedError
