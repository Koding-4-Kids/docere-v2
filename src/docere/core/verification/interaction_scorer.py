"""Heuristic interaction scoring (no LLM calls needed)."""


class HeuristicScorer:
    """Lightweight heuristic scoring for immediate feedback."""

    def score_clarity(self, response: str, question_complexity: int) -> float:
        """Score clarity based on readability and response length vs complexity."""
        # TODO: Flesch-Kincaid readability, length ratio
        raise NotImplementedError

    def score_engagement_from_timing(
        self,
        time_to_followup_seconds: int | None,
    ) -> float:
        """Estimate engagement from how quickly student responded."""
        # TODO: Fast followup = engaged, long delay or no followup = disengaged
        raise NotImplementedError
