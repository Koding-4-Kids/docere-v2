"""LangGraph tutoring agent: stateful graph replacing the hand-rolled TutoringAgent.

Graph flow:
  START → load_context → select_strategy → build_prompt → generate_response
        → parse_output → persist_messages → END
                                              ↓ (background branch)
                            score_previous → extract_concepts → update_metrics
                                           → summarize_stale → persist_flashcards
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Any

import structlog
from langgraph.graph import END, START, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from docere.core.graphs.nodes.llm import build_prompt, generate_response
from docere.core.graphs.nodes.memory import (
    extract_concepts,
    load_context,
    summarize_stale,
    update_metrics,
)
from docere.core.graphs.nodes.parsing import parse_output
from docere.core.graphs.nodes.persistence import persist_flashcards, persist_messages
from docere.core.graphs.nodes.scoring import score_previous
from docere.core.graphs.nodes.strategy import select_strategy
from docere.core.graphs.state import TutoringState
from docere.integrations.llm.client import ClaudeClient
from docere.integrations.vector_db.qdrant import QdrantStore

logger = structlog.get_logger()


@dataclass
class TutoringResult:
    """Return value from the tutoring graph invocation."""

    content: str
    model_used: str
    token_count: int
    strategy_used: str | None
    memory_context_size: int
    artifact: dict | None = None
    action: dict | None = None
    widgets: list[dict] | None = None


def build_tutoring_graph() -> StateGraph:
    """Build the LangGraph tutoring agent graph."""
    graph = StateGraph(TutoringState)

    # ── Register nodes ──
    graph.add_node("load_context", load_context)
    graph.add_node("select_strategy", select_strategy)
    graph.add_node("build_prompt", build_prompt)
    graph.add_node("generate_response", generate_response)
    graph.add_node("parse_output", parse_output)
    graph.add_node("persist_messages", persist_messages)

    # ── Critical path edges ──
    graph.add_edge(START, "load_context")
    graph.add_edge("load_context", "select_strategy")
    graph.add_edge("select_strategy", "build_prompt")
    graph.add_edge("build_prompt", "generate_response")
    graph.add_edge("generate_response", "parse_output")
    graph.add_edge("parse_output", "persist_messages")
    graph.add_edge("persist_messages", END)

    return graph


# Compile once at module level
_tutoring_graph = build_tutoring_graph().compile()


async def run_tutoring_graph(
    *,
    db: AsyncSession,
    qdrant: QdrantStore,
    claude: ClaudeClient,
    conversation_id: str,
    student_message: str,
    student_id: str,
    course_id: str,
    assignment_id: str | None = None,
    study_group: str | None = None,
) -> TutoringResult:
    """Run the tutoring graph and return a structured result.

    This replaces TutoringAgent.handle_message() with the same behavior
    but using LangGraph for state management and observability.
    """
    # Build initial state with injected dependencies
    initial_state: dict[str, Any] = {
        "student_id": student_id,
        "course_id": course_id,
        "conversation_id": conversation_id,
        "message": student_message,
        "assignment_id": assignment_id,
        "study_group": study_group,
        # Injected dependencies (prefixed with _ to indicate they're not graph state)
        "_db": db,
        "_qdrant": qdrant,
        "_claude": claude,
    }

    # Run the critical path (user-facing, fast)
    final_state = await _tutoring_graph.ainvoke(initial_state)

    strategy = final_state.get("strategy")
    memory_ctx = final_state.get("memory_context")

    logger.info(
        "Tutoring graph completed",
        conversation_id=conversation_id,
        strategy=strategy.name if strategy else None,
        memory_tokens=memory_ctx.total_tokens if memory_ctx else 0,
    )

    # Fire-and-forget: background post-processing
    # Pass only the data the background needs — NOT the request DB session,
    # which may be closed by the time the task runs.
    bg_snapshot = {k: v for k, v in final_state.items() if not k.startswith("_")}
    bg_snapshot["_qdrant"] = qdrant
    bg_snapshot["_claude"] = claude
    asyncio.create_task(_run_background(bg_snapshot))

    return TutoringResult(
        content=final_state.get("chat_text", ""),
        model_used=claude.default_model,
        token_count=len(final_state.get("response_text", "")) // 4,
        strategy_used=strategy.name if strategy else None,
        memory_context_size=memory_ctx.total_tokens if memory_ctx else 0,
        artifact=final_state.get("artifact"),
        action=final_state.get("action"),
        widgets=final_state.get("widgets") or None,
    )


async def stream_tutoring_graph(
    *,
    db: AsyncSession,
    qdrant: QdrantStore,
    claude: ClaudeClient,
    conversation_id: str,
    student_message: str,
    student_id: str,
    course_id: str,
    assignment_id: str | None = None,
    study_group: str | None = None,
) -> AsyncGenerator[dict[str, Any], None]:
    """Stream the tutoring graph, yielding token chunks then a final done event.

    Yields dicts with an "event" key:
      {"event": "token", "text": "..."}
      {"event": "done", "message_id": "...", "artifact": ..., "action": ..., ...}
      {"event": "error", "detail": "..."}
    """
    state: dict[str, Any] = {
        "student_id": student_id,
        "course_id": course_id,
        "conversation_id": conversation_id,
        "message": student_message,
        "assignment_id": assignment_id,
        "study_group": study_group,
        "_db": db,
        "_qdrant": qdrant,
        "_claude": claude,
    }

    try:
        # ── Pre-LLM nodes (fast, ~100ms total) ──
        state.update(await load_context(state))
        state.update(await select_strategy(state))
        state.update(build_prompt(state))

        # ── Stream LLM response ──
        history = state.get("history", [])
        messages = [*history, {"role": "user", "content": student_message}]
        full_text_parts: list[str] = []

        async for chunk in claude.stream(
            system_prompt=state["system_prompt"],
            messages=messages,
            max_tokens=2048,
            temperature=0.7,
        ):
            full_text_parts.append(chunk)
            yield {"event": "token", "text": chunk}

        response_text = "".join(full_text_parts)
        state["response_text"] = response_text

        # ── Post-LLM nodes on the full text ──
        state.update(parse_output(state))
        state.update(await persist_messages(state))

        strategy = state.get("strategy")
        memory_ctx = state.get("memory_context")

        logger.info(
            "Streaming tutoring graph completed",
            conversation_id=conversation_id,
            strategy=strategy.name if strategy else None,
            memory_tokens=memory_ctx.total_tokens if memory_ctx else 0,
        )

        assistant_msg_id = state.get("assistant_msg_id")
        if not assistant_msg_id:
            logger.warning(
                "assistant_msg_id missing after persist_messages",
                conversation_id=conversation_id,
            )

        yield {
            "event": "done",
            "message_id": assistant_msg_id,
            "chat_text": state.get("chat_text", ""),
            "artifact": state.get("artifact"),
            "action": state.get("action"),
            "widgets": state.get("widgets") or [],
            "strategy_used": strategy.name if strategy else None,
        }

        # Fire-and-forget: pass only data — NOT the request DB session.
        bg_snapshot = {k: v for k, v in state.items() if not k.startswith("_")}
        bg_snapshot["_qdrant"] = qdrant
        bg_snapshot["_claude"] = claude
        asyncio.create_task(_run_background(bg_snapshot))

    except Exception as e:
        logger.error("Streaming tutoring graph failed", error=str(e))
        yield {"event": "error", "detail": str(e)}


async def _run_background(state: dict[str, Any]) -> None:
    """Run background post-processing nodes (scoring, concepts, summarization).

    Uses a fresh DB session since the request session may be closed.
    """
    from docere.dependencies import async_session

    try:
        async with async_session() as db:
            bg_state = {**state, "_db": db}

            await score_previous(bg_state)
            await extract_concepts(bg_state)

            # Merge extracted concepts back for metric updates
            bg_state["extracted_concepts"] = bg_state.get("extracted_concepts", [])
            bg_state["confusion_score"] = bg_state.get("confusion_score", 0.0)
            bg_state["sentiment"] = bg_state.get("sentiment", "neutral")

            await update_metrics(bg_state)
            await summarize_stale(bg_state)
            await persist_flashcards(bg_state)

            await db.commit()
    except Exception as e:
        logger.error("Background post-processing failed", error=str(e))
