"""Outcome tracker: links interaction scores to LMS grade outcomes."""

import re
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from docere.core.improvement.strategy_archive import StrategyArchive
from docere.models.conversation import Conversation, Message
from docere.models.verification import InteractionScore

logger = structlog.get_logger()


class OutcomeTracker:
    """Tracks post-interaction outcomes from LMS grade data."""

    def __init__(self, db: AsyncSession, strategy_archive: StrategyArchive | None = None):
        self.db = db
        self.strategy_archive = strategy_archive

    async def link_grade_to_interactions(
        self,
        student_id: str,
        course_id: str,
        assignment_id: str,
        score: float,
        max_score: float,
        concepts: list[str],
        lookback_days: int = 14,
    ) -> tuple[int, list[str]]:
        """Find recent conversations about the graded topic and update scores.

        When a grade arrives from the LMS, find all tutoring interactions
        from the past N days about related concepts and record the
        subsequent_performance on their interaction scores.

        Returns number of interaction_scores updated.
        """
        percentage = score / max_score if max_score > 0 else 0
        cutoff = datetime.now(UTC) - timedelta(days=lookback_days)

        # Find recent conversations in this course
        conv_result = await self.db.execute(
            select(Conversation.id).where(
                Conversation.student_id == student_id,
                Conversation.course_id == course_id,
                Conversation.started_at >= cutoff,
            )
        )
        conversation_ids = [row[0] for row in conv_result.all()]

        if not conversation_ids:
            return 0

        # Find interaction scores for these conversations
        score_result = await self.db.execute(
            select(InteractionScore).where(
                InteractionScore.conversation_id.in_(conversation_ids),
                InteractionScore.student_id == student_id,
                InteractionScore.subsequent_performance.is_(None),
            )
        )
        scores = score_result.scalars().all()

        updated = 0
        updated_ids: list[str] = []
        for interaction_score in scores:
            # Check if the message content relates to the graded concepts
            msg_result = await self.db.execute(
                select(Message.content).where(Message.id == interaction_score.message_id)
            )
            msg_content = msg_result.scalar_one_or_none()

            if msg_content and self._content_matches_concepts(msg_content, concepts):
                interaction_score.subsequent_performance = percentage
                updated += 1
                updated_ids.append(str(interaction_score.id))

        if updated:
            await self.db.flush()
            logger.info(
                "Linked grade to interactions",
                student_id=student_id,
                assignment_id=assignment_id,
                score=f"{score}/{max_score}",
                interactions_updated=updated,
            )

            # Feed grade signal back into strategy scores
            if self.strategy_archive:
                for score_id in updated_ids:
                    await self.strategy_archive.incorporate_grade_signal(score_id, percentage)

        return updated, updated_ids

    def _content_matches_concepts(self, content: str, concepts: list[str]) -> bool:
        """Check if message content relates to any of the given concepts."""
        content_lower = content.lower()
        for concept in concepts:
            c = concept.lower()
            if " " in c:
                # Multi-word concepts: substring match is specific enough
                if c in content_lower:
                    return True
            else:
                # Single-word concepts: use word boundary to avoid false matches
                if re.search(r"\b" + re.escape(c) + r"\b", content_lower):
                    return True
        return False
