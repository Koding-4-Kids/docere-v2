"""Shared state schemas for LangGraph agents."""

from __future__ import annotations

from typing import Any, TypedDict


class TutoringState(TypedDict, total=False):
    """State for the tutoring agent graph."""

    # ── Injected dependencies (passed through graph, not serialized) ──
    _db: Any  # AsyncSession
    _qdrant: Any  # QdrantStore
    _claude: Any  # ClaudeClient

    # ── Input (set by caller) ──
    student_id: str
    course_id: str
    conversation_id: str
    message: str
    assignment_id: str | None
    study_group: str | None

    # ── Loaded context ──
    history: list[dict[str, str]]
    memory_context: Any  # MemoryContext object
    student_profile: Any  # StudentProfile object
    assignment: Any  # Assignment object | None

    # ── Strategy ──
    strategy: Any  # Strategy object | None
    strategy_context: Any  # StrategyContext | None

    # ── LLM ──
    system_prompt: str
    response_text: str

    # ── Parsed output ──
    chat_text: str
    artifact: dict[str, Any] | None
    action: dict[str, Any] | None
    widgets: list[dict[str, Any]]

    # ── Persisted ──
    assistant_msg_id: str | None

    # ── Background results ──
    extracted_concepts: list[str]
    confusion_score: float
    sentiment: str


class ClassroomState(TypedDict, total=False):
    """State for the classroom agent graph."""

    # ── Injected dependencies (passed through graph, not serialized) ──
    _db: Any  # AsyncSession
    _qdrant: Any  # QdrantStore
    _claude: Any  # ClaudeClient

    # ── Input ──
    course_id: str
    question: str
    history: list[dict[str, str]]
    source_filters: dict[str, bool]
    integration_instructions: str

    # ── Data ──
    context: Any  # ClassroomContext
    routing: Any  # RoutingDecision
    mastery_by_student: dict[str, dict[str, float]]
    summaries: list[Any]  # list[StudentSummary]
    sources: list[Any]  # list[SourceRef]

    # ── Output ──
    answer: str
    widgets: list[dict[str, Any]]
