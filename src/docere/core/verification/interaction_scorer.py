"""Heuristic interaction scoring (no LLM calls needed)."""

import re
import math


class HeuristicScorer:
    """Lightweight heuristic scoring for immediate feedback."""

    def score_clarity(self, response: str, question_length: int) -> float:
        """Score clarity based on readability and response length vs complexity.

        Factors:
        - Sentence length (shorter = clearer for tutoring)
        - Use of examples or code blocks
        - Response length relative to question complexity
        """
        sentences = re.split(r"[.!?]+", response)
        sentences = [s.strip() for s in sentences if s.strip()]

        if not sentences:
            return 0.3

        # Average sentence length (ideal: 10-20 words for tutoring)
        avg_words = sum(len(s.split()) for s in sentences) / len(sentences)
        length_score = 1.0 - min(1.0, abs(avg_words - 15) / 30)

        # Bonus for using examples or code blocks
        has_example = 1.0 if ("example" in response.lower() or "```" in response) else 0.0
        example_bonus = has_example * 0.15

        # Penalty for being too short or too long relative to question
        ratio = len(response) / max(question_length, 1)
        ratio_score = 1.0 if 1.5 <= ratio <= 8.0 else 0.7

        score = (length_score * 0.5 + ratio_score * 0.35 + example_bonus)
        return max(0.0, min(1.0, score))

    def score_engagement_from_timing(
        self,
        time_to_followup_seconds: int | None,
    ) -> float:
        """Estimate engagement from how quickly student responded.

        - < 30s: Very engaged (0.9)
        - 30s - 2min: Engaged (0.7)
        - 2min - 10min: Moderate (0.5)
        - 10min - 1hr: Low engagement (0.3)
        - > 1hr or None: Disengaged (0.1)
        """
        if time_to_followup_seconds is None:
            return 0.1

        t = time_to_followup_seconds
        if t < 30:
            return 0.9
        elif t < 120:
            return 0.7
        elif t < 600:
            return 0.5
        elif t < 3600:
            return 0.3
        else:
            return 0.1

    def score_response_quality(self, response: str) -> float:
        """Quick quality check on the response content.

        Checks for:
        - Contains a question (Socratic engagement)
        - Structured formatting (bullet points, numbered lists)
        - Appropriate length
        """
        score = 0.5

        # Bonus for asking questions (Socratic)
        if "?" in response:
            score += 0.15

        # Bonus for structured formatting
        if re.search(r"^\s*[-*•]\s", response, re.MULTILINE) or re.search(
            r"^\s*\d+[.)]\s", response, re.MULTILINE
        ):
            score += 0.1

        # Penalty for very short responses (under 50 chars)
        if len(response) < 50:
            score -= 0.2

        # Penalty for very long responses (over 2000 chars)
        if len(response) > 2000:
            score -= 0.1

        return max(0.0, min(1.0, score))
