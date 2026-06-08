"""LLM-related graph nodes: prompt building and response generation."""

from __future__ import annotations

import structlog

from docere.config import settings
from docere.core.agent import (
    BASE_SYSTEM_PROMPT,
    MEETING_KEYWORDS,
    MEETING_SCHEDULING_INSTRUCTIONS,
    STUDY_MATERIALS_INSTRUCTIONS,
    WIDGET_INSTRUCTIONS,
)
from docere.core.graphs.state import TutoringState

logger = structlog.get_logger()


def build_prompt(state: TutoringState) -> dict:
    """Assemble the full system prompt from context, strategy, and instructions."""
    memory_ctx = state.get("memory_context")
    if not memory_ctx:
        from docere.core.memory.memory_layer import MemoryContext

        memory_ctx = MemoryContext.empty()
    strategy = state.get("strategy")
    assignment = state.get("assignment")
    profile = state.get("student_profile")
    message = state["message"]

    parts = [BASE_SYSTEM_PROMPT]

    # Current assignment context
    if assignment:
        section = f"\n## Current Assignment\nTitle: {assignment.title}"
        if assignment.due_at:
            section += f"\nDue: {assignment.due_at.strftime('%Y-%m-%d %H:%M')}"
        if assignment.description:
            section += f"\nDescription: {assignment.description}"
        if assignment.points_possible is not None:
            section += f"\nPoints: {assignment.points_possible}"
        section += (
            "\n\nThe student is asking about this specific assignment. "
            "You have the full assignment details above — do NOT ask them "
            "to paste or reiterate the assignment."
        )
        parts.append(section)

    # Strategy instructions
    if strategy and hasattr(strategy, "prompt_template") and strategy.prompt_template:
        parts.append(f"\n## Teaching Strategy\n{strategy.prompt_template}")

    # Memory context
    context_str = memory_ctx.to_system_context()
    if context_str:
        parts.append(f"\n## Student Context\n{context_str}")

    # Score-based adaptation
    if profile:
        adaptations = []
        if (profile.avg_interaction_score or 0) < 0.4 and profile.total_interactions >= 3:
            adaptations.append(
                "Previous approaches haven't been effective with this student. "
                "Try a completely different angle than what might have been tried before."
            )
        if (profile.avg_confusion_score or 0) > 0.6 and profile.engagement_level != "high":
            adaptations.append(
                "This student is frequently confused. Use very short, concrete "
                "examples. Avoid abstract explanations."
            )
        if adaptations:
            parts.append("\n## Adaptation Notes\n" + "\n".join(adaptations))

    # Student-uploaded documents
    student_doc_ctx = state.get("student_doc_context", "")
    if student_doc_ctx:
        parts.append(f"\n## Student's Uploaded Materials\n{student_doc_ctx}")

    # Live notes from the student's editor
    notes = state.get("notes_content") or ""
    notes = notes.strip()
    if notes:
        parts.append(
            f"\n## Student's Current Notes\n"
            f"The student is actively editing these notes right now. "
            f"Reference them when relevant — correct mistakes, fill gaps, "
            f"or build on what they've written.\n\n{notes}"
        )

    parts.append(STUDY_MATERIALS_INSTRUCTIONS)
    parts.append(WIDGET_INSTRUCTIONS)

    # Meeting scheduling
    suggest_meeting = _should_suggest_meeting(profile, message)
    if suggest_meeting:
        parts.append(MEETING_SCHEDULING_INSTRUCTIONS)
        parts.append(
            "\n## Meeting Suggestion Active\n"
            "The student appears to be persistently struggling. "
            "Consider suggesting they schedule a meeting with their instructor."
        )

    # No materials note
    if not memory_ctx.teacher_context:
        parts.append(
            "\n## Note\n"
            "No course materials have been uploaded for this course yet. "
            "You are still connected to the student's LMS — the instructor "
            "simply hasn't added materials. Help the student with what you "
            "know and do NOT claim you lack access to their course."
        )

    return {"system_prompt": "\n".join(parts)}


async def generate_response(state: TutoringState) -> dict:
    """Call Claude to generate the tutoring response."""
    claude = state["_claude"]
    history = state.get("history", [])
    message = state["message"]

    messages = [*history, {"role": "user", "content": message}]
    response_text = await claude.chat(
        system_prompt=state["system_prompt"],
        messages=messages,
        max_tokens=2048,
        temperature=0.7,
    )

    return {"response_text": response_text}


def _should_suggest_meeting(profile: object | None, student_message: str) -> bool:
    """Determine if meeting scheduling instructions should be injected."""
    if MEETING_KEYWORDS.search(student_message):
        return True

    if profile and hasattr(profile, "avg_confusion_score"):
        if (
            profile.avg_confusion_score > settings.meeting_struggle_threshold
            and (profile.total_interactions or 0) >= settings.meeting_struggle_consecutive_count
        ):
            return True

    return False
