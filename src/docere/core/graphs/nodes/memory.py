"""Memory-related graph nodes: context loading, concept extraction, metric updates."""

from __future__ import annotations

import structlog

from docere.config import settings
from docere.core.graphs.state import TutoringState
from docere.core.memory.memory_layer import MemoryContext

logger = structlog.get_logger()


async def load_context(state: TutoringState) -> dict:
    """Load memory context, student profile, assignment, and conversation history in parallel."""
    import asyncio

    from sqlalchemy import select

    from docere.core.memory.memory_layer import MemoryLayer
    from docere.models.conversation import Message
    from docere.models.course import Assignment

    db = state["_db"]
    qdrant = state["_qdrant"]
    claude = state["_claude"]
    memory = MemoryLayer(db, qdrant, claude)

    student_id = state["student_id"]
    course_id = state["course_id"]
    conversation_id = state["conversation_id"]
    message = state["message"]
    assignment_id = state.get("assignment_id")
    study_group = state.get("study_group")

    async def _load_assignment():
        if not assignment_id:
            return None
        try:
            r = await db.execute(select(Assignment).where(Assignment.id == assignment_id))
            return r.scalar_one_or_none()
        except Exception as e:
            logger.warning("Assignment lookup failed", error=str(e))
            return None

    async def _load_memory():
        if study_group == "control":
            return MemoryContext.empty()
        try:
            return await memory.retrieve_context(
                student_id=student_id,
                course_id=course_id,
                current_query=message,
                assignment_id=assignment_id,
                max_tokens=settings.memory_max_context_tokens,
            )
        except RuntimeError as e:
            logger.warning("Memory retrieval failed, using empty context", error=str(e))
            return MemoryContext.empty()

    async def _load_profile():
        if study_group == "control":
            return None
        try:
            return await memory.profile_builder.get_profile(student_id, course_id)
        except Exception as e:
            logger.warning("Profile loading failed", error=str(e))
            return None

    async def _load_history():
        try:
            result = await db.execute(
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.created_at.desc())
                .limit(20)
            )
            messages = list(reversed(result.scalars().all()))
            return [{"role": msg.role, "content": msg.content} for msg in messages]
        except Exception as e:
            logger.warning("History loading failed", error=str(e))
            return []

    async def _load_student_docs():
        from docere.core.memory.student_documents import StudentDocumentManager

        try:
            manager = StudentDocumentManager(qdrant)
            return await manager.retrieve_relevant(student_id, course_id, message, max_chunks=3)
        except Exception as e:
            logger.warning("Student doc retrieval failed", error=str(e))
            return ""

    assignment, memory_ctx, profile, history, student_doc_ctx = await asyncio.gather(
        _load_assignment(), _load_memory(), _load_profile(), _load_history(),
        _load_student_docs(),
    )

    return {
        "assignment": assignment,
        "memory_context": memory_ctx,
        "student_profile": profile,
        "history": history,
        "student_doc_context": student_doc_ctx,
    }


async def extract_concepts(state: TutoringState) -> dict:
    """Extract concepts, confusion, and sentiment from the exchange (background)."""
    from docere.core.memory.memory_layer import MemoryLayer

    db = state["_db"]
    qdrant = state["_qdrant"]
    claude = state["_claude"]
    memory = MemoryLayer(db, qdrant, claude)

    try:
        concepts, confusion, sentiment = await memory.extract_concepts(
            student_message=state["message"],
            agent_response=state["response_text"],
        )
        return {
            "extracted_concepts": concepts,
            "confusion_score": confusion,
            "sentiment": sentiment,
        }
    except Exception as e:
        logger.warning("Concept extraction failed", error=str(e))
        return {"extracted_concepts": [], "confusion_score": 0.0, "sentiment": "neutral"}


async def update_metrics(state: TutoringState) -> dict:
    """Update StudentProfile + ConceptMastery from extracted concepts (background)."""
    from docere.core.memory.memory_layer import MemoryLayer

    db = state["_db"]
    qdrant = state["_qdrant"]
    claude = state["_claude"]
    memory = MemoryLayer(db, qdrant, claude)

    try:
        await memory.update_live_metrics(
            student_id=state["student_id"],
            course_id=state["course_id"],
            concepts=state.get("extracted_concepts", []),
            confusion_score=state.get("confusion_score", 0.0),
            sentiment=state.get("sentiment", "neutral"),
        )
    except Exception as e:
        logger.warning("Metric update failed", error=str(e))

    return {}


async def summarize_stale(state: TutoringState) -> dict:
    """Summarize conversations idle for 1+ hours (background)."""
    from docere.core.memory.memory_layer import MemoryLayer

    if state.get("study_group") == "control":
        return {}

    db = state["_db"]
    qdrant = state["_qdrant"]
    claude = state["_claude"]
    memory = MemoryLayer(db, qdrant, claude)

    try:
        await memory.summarize_stale_conversations(
            student_id=state["student_id"],
            course_id=state["course_id"],
        )
    except Exception as e:
        logger.warning("Stale summarization failed", error=str(e))

    return {}
