"""Process verification module: scores each tutoring interaction.

Adapts MATH-SHEPHERD's process reward model approach to open-ended
educational dialogues. Instead of verifying math steps, we score
whether tutoring interactions actually helped the student learn.

Scoring dimensions:
- helpfulness (0-1): Did the response address the student's actual need?
- clarity (0-1): Was the explanation clear for this student's level?
- engagement (0-1): Did the student continue engaging productively?
- understanding_delta (-1 to 1): Did understanding improve?
"""

from dataclasses import dataclass


@dataclass
class InteractionScore:
    """Scores for a single tutoring interaction."""

    helpfulness_score: float
    clarity_score: float
    engagement_score: float
    understanding_delta: float
    composite_score: float
    student_followup_type: str  # 'understood' | 'still_confused' | 'new_question' | 'none'
    scoring_method: str  # 'llm_judge' | 'heuristic' | 'hybrid'


class ProcessVerifier:
    """Scores tutoring interactions for educational effectiveness."""

    async def score_interaction(
        self,
        message_id: str,
        assistant_message: str,
        student_followup: str | None,
        student_context: dict[str, object],
        time_to_followup: int | None = None,
    ) -> InteractionScore:
        """Score a tutoring interaction using LLM-as-judge + heuristics.

        Phase 1 (immediate): Heuristic scoring based on readability, length
        Phase 2 (deferred): Full scoring after student responds or times out

        Composite = 0.35*helpfulness + 0.25*clarity + 0.25*understanding + 0.15*engagement
        """
        # TODO: Implement scoring pipeline
        raise NotImplementedError

    async def classify_followup(
        self,
        assistant_message: str,
        student_followup: str,
    ) -> str:
        """Classify student followup as understood/still_confused/new_question.

        Uses Claude to analyze whether the student's next message indicates
        they understood, are still confused, or moved to a deeper question.
        """
        # TODO: Call Claude with classification prompt
        raise NotImplementedError
