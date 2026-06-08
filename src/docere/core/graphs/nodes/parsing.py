"""Output parsing graph nodes: extract artifacts, actions, widgets from LLM response."""

from __future__ import annotations

from typing import Any

import structlog

from docere.core.agent import MEETING_KEYWORDS, TutoringAgent
from docere.core.graphs.state import TutoringState

logger = structlog.get_logger()


def parse_output(state: TutoringState) -> dict[str, Any]:
    """Extract artifact, action, and widget blocks from the LLM response text."""
    response_text = state["response_text"]
    message = state["message"]
    profile = state.get("student_profile")
    memory_ctx = state.get("memory_context")

    # Reuse the static extraction methods from the original TutoringAgent
    chat_text, artifact = TutoringAgent._extract_artifact(response_text)
    chat_text, action = TutoringAgent._extract_action(chat_text)
    chat_text, widgets = TutoringAgent._extract_widgets(chat_text)

    # Force-inject meeting action if student explicitly asked but LLM missed it
    explicit_meeting = bool(MEETING_KEYWORDS.search(message))
    if explicit_meeting and not action:
        struggle_concepts: list[str] = []
        if profile and hasattr(profile, "top_confused_concepts"):
            struggle_concepts = profile.top_confused_concepts or []
        elif memory_ctx and hasattr(memory_ctx, "concepts"):
            struggle_concepts = list(memory_ctx.concepts or [])

        action = {
            "type": "meeting_suggestion",
            "reason": "You'd like to meet with your instructor — let's get that scheduled.",
            "concepts": struggle_concepts[:5],
        }
        logger.info("Force-injected meeting action for explicit request")

    return {
        "chat_text": chat_text,
        "artifact": artifact,
        "action": action,
        "widgets": widgets or [],
    }
