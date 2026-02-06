"""Student profile builder: tracks learning patterns and generates narrative summaries."""


class StudentProfileBuilder:
    """Builds and maintains student learning profiles."""

    async def get_profile(self, student_id: str, course_id: str) -> dict[str, object]:
        """Get the current student profile."""
        # TODO: Fetch from PostgreSQL
        raise NotImplementedError

    async def update_from_interaction(
        self,
        student_id: str,
        course_id: str,
        concepts: list[str],
        confusion_score: float,
        sentiment: str,
    ) -> None:
        """Update profile after an interaction."""
        # TODO: Update concept mastery, interaction counts, aggregate stats
        raise NotImplementedError

    async def generate_narrative_summary(self, student_id: str, course_id: str) -> str:
        """Generate a narrative profile summary via Claude.

        Example: 'Sarah has been struggling with recursion for 2 weeks.
        She responds well to visual analogies. Her grades on recursion-related
        assignments are below class average.'
        """
        # TODO: Gather data, call Claude to generate narrative
        raise NotImplementedError
