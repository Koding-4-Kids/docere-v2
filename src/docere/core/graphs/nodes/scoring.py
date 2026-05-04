"""Interaction scoring graph node (background)."""

from __future__ import annotations

from datetime import UTC, datetime

import structlog
from sqlalchemy import select

from docere.core.graphs.state import TutoringState
from docere.core.improvement.strategy_archive import StrategyArchive, StrategyContext
from docere.core.verification.process_verifier import ProcessVerifier
from docere.models.conversation import Message
from docere.models.memory import MemoryRecord

logger = structlog.get_logger()


async def score_previous(state: TutoringState) -> dict:
    """Score the previous assistant message now that we have the student's followup."""
    if state.get("study_group") == "control":
        return {}

    db = state["_db"]
    claude = state["_claude"]
    conversation_id = state["conversation_id"]
    student_id = state["student_id"]
    course_id = state["course_id"]
    student_followup = state["message"]

    try:
        verifier = ProcessVerifier(db, claude)
        strategies = StrategyArchive(db)

        # Find the student's current message (the followup we're using to judge)
        result = await db.execute(
            select(Message)
            .where(
                Message.conversation_id == conversation_id,
                Message.role == "user",
            )
            .order_by(Message.created_at.desc())
            .limit(1)
        )
        current_student_msg = result.scalar_one_or_none()
        if not current_student_msg:
            return {}

        # Find the assistant message BEFORE the current student message
        # (this is the one we want to score — the student's followup tells us if it helped)
        result = await db.execute(
            select(Message)
            .where(
                Message.conversation_id == conversation_id,
                Message.role == "assistant",
                Message.created_at < current_student_msg.created_at,
            )
            .order_by(Message.created_at.desc())
            .limit(1)
        )
        prev_assistant = result.scalar_one_or_none()
        if not prev_assistant:
            return {}

        # Find the student message that prompted the previous assistant response
        result = await db.execute(
            select(Message)
            .where(
                Message.conversation_id == conversation_id,
                Message.role == "user",
                Message.created_at <= prev_assistant.created_at,
            )
            .order_by(Message.created_at.desc())
            .limit(1)
        )
        prev_student = result.scalar_one_or_none()
        if not prev_student:
            return {}

        # Time from assistant response to student's followup (not to "now")
        time_delta = int((current_student_msg.created_at - prev_assistant.created_at).total_seconds())

        verification = await verifier.score_interaction(
            message_id=str(prev_assistant.id),
            conversation_id=conversation_id,
            student_id=student_id,
            student_message=prev_student.content,
            assistant_message=prev_assistant.content,
            student_followup=student_followup,
            time_to_followup=time_delta,
        )

        # Update profile avg_interaction_score
        from docere.core.memory.memory_layer import MemoryLayer

        qdrant = state["_qdrant"]
        memory = MemoryLayer(db, qdrant, claude)
        profile = await memory.profile_builder.get_profile(student_id, course_id)
        if profile:
            n = profile.total_interactions or 1
            old_avg = profile.avg_interaction_score or 0.0
            profile.avg_interaction_score = (old_avg * (n - 1) + verification.composite_score) / n

        # Record outcome for strategy bandit
        metadata = prev_assistant.metadata_ or {}
        strategy_id = metadata.get("strategy_id")
        if strategy_id:
            mem_result = await db.execute(
                select(MemoryRecord.concepts)
                .where(MemoryRecord.source_message_id == prev_assistant.id)
                .limit(1)
            )
            concepts = mem_result.scalar_one_or_none() or []

            context_key = metadata.get("strategy_context_key")
            strategy_ctx = None
            if context_key:
                parts = context_key.split(":")
                if len(parts) == 3:
                    strategy_ctx = StrategyContext(*parts)

            await strategies.record_outcome(
                strategy_id=strategy_id,
                conversation_id=conversation_id,
                score=verification.composite_score,
                interaction_score_id=verification.score_id,
                context_metadata={
                    "concepts": concepts,
                    "concept": concepts[0] if concepts else None,
                    "student_id": student_id,
                    "followup_type": verification.student_followup_type,
                    "helpfulness": verification.helpfulness_score,
                    "clarity": verification.clarity_score,
                    "engagement": verification.engagement_score,
                    "understanding_delta": verification.understanding_delta,
                },
                context=strategy_ctx,
            )

        logger.info(
            "Previous interaction scored",
            message_id=str(prev_assistant.id),
            composite=f"{verification.composite_score:.2f}",
        )
    except Exception as e:
        logger.warning("Background scoring failed", error=str(e))

    return {}
