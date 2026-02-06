"""Outcome tracker: links interaction scores to LMS grade outcomes."""


class OutcomeTracker:
    """Tracks post-interaction outcomes from LMS grade data."""

    async def link_grade_to_interactions(
        self,
        student_id: str,
        course_id: str,
        assignment_id: str,
        score: float,
        concepts: list[str],
    ) -> int:
        """Find recent conversations about the graded topic and update scores.

        Returns number of interaction_scores updated with subsequent_performance.
        """
        # TODO: Find recent conversations matching concepts, update scores
        raise NotImplementedError
