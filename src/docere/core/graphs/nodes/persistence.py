"""Persistence graph nodes: save messages and flashcards."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import select

from docere.core.graphs.state import TutoringState
from docere.models.conversation import Conversation, Message

logger = structlog.get_logger()


async def persist_messages(state: TutoringState) -> dict[str, Any]:
    """Save user + assistant messages to the database and commit."""
    db = state["_db"]
    conversation_id = state["conversation_id"]
    now = datetime.now(UTC)

    strategy = state.get("strategy")
    strategy_ctx = state.get("strategy_context")
    memory_ctx = state.get("memory_context")

    student_msg = Message(
        conversation_id=conversation_id,
        role="user",
        content=state["message"],
        created_at=now,
    )
    db.add(student_msg)

    assistant_msg = Message(
        conversation_id=conversation_id,
        role="assistant",
        content=state["chat_text"],
        model_used=state["_claude"].default_model,
        token_count=len(state.get("response_text", "")) // 4,
        metadata_={
            "strategy_id": str(strategy.id) if strategy else None,
            "strategy_name": strategy.name if strategy else None,
            "memory_tokens": memory_ctx.total_tokens if memory_ctx else 0,
            "strategy_context_key": strategy_ctx.key if strategy_ctx else None,
            "artifact": state.get("artifact"),
            "action": state.get("action"),
            "widgets": state.get("widgets") or None,
        },
        created_at=now,
    )
    db.add(assistant_msg)

    # Update conversation timestamp
    result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
    conversation = result.scalar_one_or_none()
    if conversation:
        conversation.last_message_at = now
        if strategy:
            conversation.strategy_id = strategy.id

    await db.commit()

    logger.info(
        "Messages persisted",
        conversation_id=conversation_id,
        strategy=strategy.name if strategy else None,
    )

    return {"assistant_msg_id": str(assistant_msg.id)}


async def persist_flashcards(state: TutoringState) -> dict[str, Any]:
    """Persist flashcard artifacts to the student's deck (background)."""
    artifact = state.get("artifact")
    if not artifact or artifact.get("type") != "flashcards":
        return {}

    db = state["_db"]

    try:
        from docere.services.flashcard_service import FlashcardService

        svc = FlashcardService(db)
        raw_content = artifact.get("content", "[]")
        cards_json = json.loads(raw_content) if isinstance(raw_content, str) else raw_content
        added = await svc.add_cards_from_artifact(
            student_id=state["student_id"],
            course_id=state["course_id"],
            cards_json=cards_json,
            source_message_id=state.get("assistant_msg_id"),
            concepts=artifact.get("source_concepts", []),
        )
        if added:
            logger.info("Flashcards persisted", count=added)
    except Exception as e:
        logger.warning("Failed to persist flashcard artifact", error=str(e))

    return {}
