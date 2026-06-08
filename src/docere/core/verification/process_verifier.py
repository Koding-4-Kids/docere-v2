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

import json
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from docere.config import settings
from docere.core.verification.interaction_scorer import HeuristicScorer
from docere.integrations.llm.client import ClaudeClient
from docere.models.verification import InteractionScore as InteractionScoreModel

logger = structlog.get_logger()

CLASSIFY_FOLLOWUP_PROMPT = """Classify the student's followup message after receiving a tutor's response.

Tutor's response:
{assistant_message}

Student's followup:
{student_followup}

Classify as exactly one of:
- "understood": Student shows understanding, thanks the tutor, or moves on confidently
- "still_confused": Student asks the same question again, says they don't get it, or shows continued confusion
- "new_question": Student asks a deeper or related question (indicates partial understanding)
- "off_topic": Student changes subject entirely

Respond with ONLY the classification word, nothing else."""

JUDGE_PROMPT = """You are evaluating a tutoring interaction for educational effectiveness.

Student's question:
{student_message}

Tutor's response:
{assistant_message}

Student profile context:
{student_context}

{followup_section}

Score each dimension from 0.0 to 1.0 (understanding_delta from -1.0 to 1.0):

1. helpfulness: Did the response address the student's actual need? (0=unhelpful, 1=perfectly addressed)
2. clarity: Was the explanation clear and appropriate for this student? (0=confusing, 1=crystal clear)
3. engagement: Does the response encourage continued productive learning? (0=disengaging, 1=highly engaging)
4. understanding_delta: How much did the student's understanding likely change? (-1=more confused, 0=no change, 1=full understanding gained)

Respond with ONLY a JSON object:
{{"helpfulness": 0.0, "clarity": 0.0, "engagement": 0.0, "understanding_delta": 0.0}}"""


@dataclass
class VerificationResult:
    """Scores for a single tutoring interaction."""

    helpfulness_score: float
    clarity_score: float
    engagement_score: float
    understanding_delta: float
    composite_score: float
    student_followup_type: str
    scoring_method: str
    score_id: str | None = None


class ProcessVerifier:
    """Scores tutoring interactions for educational effectiveness."""

    def __init__(self, db: AsyncSession, claude: ClaudeClient):
        self.db = db
        self.claude = claude
        self.heuristic = HeuristicScorer()

    async def score_interaction(
        self,
        message_id: str,
        conversation_id: str,
        student_id: str,
        student_message: str,
        assistant_message: str,
        student_followup: str | None = None,
        student_context: str = "",
        time_to_followup: int | None = None,
    ) -> VerificationResult:
        """Score a tutoring interaction using LLM-as-judge + heuristics.

        Phase 1 (immediate): Heuristic scoring based on readability, length
        Phase 2 (deferred): Full scoring after student responds or times out

        Composite = 0.35*helpfulness + 0.25*clarity + 0.25*understanding + 0.15*engagement
        """
        # Classify followup if available
        followup_type = "none"
        if student_followup:
            followup_type = await self.classify_followup(assistant_message, student_followup)

        # Get heuristic scores
        h_clarity = self.heuristic.score_clarity(assistant_message, len(student_message))
        h_engagement = self.heuristic.score_engagement_from_timing(time_to_followup)
        h_quality = self.heuristic.score_response_quality(assistant_message)

        # Get LLM-as-judge scores
        llm_scores = await self._llm_judge(
            student_message=student_message,
            assistant_message=assistant_message,
            student_context=student_context,
            student_followup=student_followup,
            followup_type=followup_type,
        )

        # Hybrid: blend LLM and heuristic scores
        if llm_scores:
            helpfulness = llm_scores["helpfulness"]
            clarity = llm_scores["clarity"] * 0.7 + h_clarity * 0.3
            engagement = llm_scores["engagement"] * 0.6 + h_engagement * 0.4
            understanding = llm_scores["understanding_delta"]
            method = "hybrid"
        else:
            helpfulness = h_quality
            clarity = h_clarity
            engagement = h_engagement
            understanding = self._infer_understanding(followup_type)
            method = "heuristic"

        # Composite score using configured weights
        composite = (
            settings.verification_helpfulness_weight * helpfulness
            + settings.verification_clarity_weight * clarity
            + settings.verification_understanding_weight * max(0, understanding)
            + settings.verification_engagement_weight * engagement
        )

        # Persist to database
        score_record = InteractionScoreModel(
            message_id=message_id,
            conversation_id=conversation_id,
            student_id=student_id,
            helpfulness_score=helpfulness,
            clarity_score=clarity,
            engagement_score=engagement,
            understanding_delta=understanding,
            student_followup_type=followup_type,
            time_to_next_message_seconds=time_to_followup,
            composite_score=composite,
            scoring_method=method,
        )
        self.db.add(score_record)
        await self.db.flush()

        logger.info(
            "Interaction scored",
            message_id=message_id,
            composite=f"{composite:.2f}",
            method=method,
            followup_type=followup_type,
        )

        return VerificationResult(
            helpfulness_score=helpfulness,
            clarity_score=clarity,
            engagement_score=engagement,
            understanding_delta=understanding,
            composite_score=composite,
            student_followup_type=followup_type,
            scoring_method=method,
            score_id=str(score_record.id),
        )

    async def classify_followup(
        self,
        assistant_message: str,
        student_followup: str,
    ) -> str:
        """Classify student followup as understood/still_confused/new_question/off_topic."""
        prompt = CLASSIFY_FOLLOWUP_PROMPT.format(
            assistant_message=assistant_message[:500],
            student_followup=student_followup[:500],
        )

        result = await self.claude.chat(
            system_prompt="You are a student response classifier.",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=20,
            temperature=0.1,
        )

        classification = result.strip().lower().strip('"')
        valid = {"understood", "still_confused", "new_question", "off_topic"}
        return classification if classification in valid else "none"

    async def _llm_judge(
        self,
        student_message: str,
        assistant_message: str,
        student_context: str,
        student_followup: str | None,
        followup_type: str,
    ) -> dict[str, float] | None:
        """Get LLM-as-judge scores. Returns None if the call fails."""
        followup_section = ""
        if student_followup:
            followup_section = (
                f"Student's followup (classified as '{followup_type}'):\n{student_followup[:500]}"
            )

        prompt = JUDGE_PROMPT.format(
            student_message=student_message[:500],
            assistant_message=assistant_message[:1000],
            student_context=student_context[:500] or "No profile available yet.",
            followup_section=followup_section,
        )

        try:
            result = await self.claude.chat(
                system_prompt="You are an educational interaction evaluator. Respond with only JSON.",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=100,
                temperature=0.2,
            )
            scores = json.loads(result.strip())
            # Validate ranges
            return {
                "helpfulness": max(0.0, min(1.0, float(scores.get("helpfulness", 0.5)))),
                "clarity": max(0.0, min(1.0, float(scores.get("clarity", 0.5)))),
                "engagement": max(0.0, min(1.0, float(scores.get("engagement", 0.5)))),
                "understanding_delta": max(
                    -1.0, min(1.0, float(scores.get("understanding_delta", 0.0)))
                ),
            }
        except (json.JSONDecodeError, KeyError, ValueError):
            logger.warning("LLM judge failed to return valid scores")
            return None

    def _infer_understanding(self, followup_type: str) -> float:
        """Infer understanding delta from followup classification."""
        mapping = {
            "understood": 0.7,
            "new_question": 0.3,
            "still_confused": -0.3,
            "off_topic": 0.0,
            "none": 0.0,
        }
        return mapping.get(followup_type, 0.0)
