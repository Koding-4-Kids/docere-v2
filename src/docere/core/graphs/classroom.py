"""LangGraph classroom agent: stateful graph replacing the hand-rolled ClassroomAgent.

Graph flow:
  START → load_classroom → route_intent →(conditional)→ ...
    META → synthesize_meta → build_meta_widgets → END
    TOPIC → find_topic_students → load_mastery → build_summaries → synthesize → build_widgets → END
    OTHER → load_mastery → build_summaries → synthesize → build_widgets → END
"""

from __future__ import annotations

from typing import Any

import structlog
from langgraph.graph import END, START, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from docere.core.classroom_agent import (
    ClassroomAgent,
    ClassroomResponse,
    QueryIntent,
    RoutingDecision,
    SourceRef,
)
from docere.core.graphs.state import ClassroomState
from docere.integrations.llm.client import ClaudeClient
from docere.integrations.vector_db.qdrant import QdrantStore

logger = structlog.get_logger()


# ── Node functions ──


async def load_classroom(state: ClassroomState) -> dict:
    """Load roster + profiles + concept overview."""
    db = state["_db"]
    qdrant = state["_qdrant"]
    claude = state["_claude"]
    agent = ClassroomAgent(db, qdrant, claude)

    filters = state.get("source_filters", {})
    context = await agent._load_classroom_context(
        state["course_id"],
        include_profiles=filters.get("profiles", True),
        include_concepts=filters.get("mastery", True),
    )

    sources: list[SourceRef] = [
        SourceRef(type="enrollment", label=f"Student roster ({context.total_students} enrolled)")
    ]

    return {"context": context, "sources": sources}


def route_intent(state: ClassroomState) -> dict:
    """Heuristic intent classification — no LLM call."""
    db = state["_db"]
    qdrant = state["_qdrant"]
    claude = state["_claude"]
    agent = ClassroomAgent(db, qdrant, claude)

    context = state["context"]
    question = state["question"]

    if context.total_students == 0:
        return {
            "routing": RoutingDecision(
                intent=QueryIntent.META,
                target_student_ids=[],
                target_student_names=[],
                reasoning="No students enrolled",
            )
        }

    routing = agent._route_heuristic(question, context)

    sources = list(state.get("sources", []))
    sources.append(
        SourceRef(
            type="routing",
            label=f"Query type: {routing.intent.value}",
            detail=routing.reasoning,
        )
    )

    logger.info(
        "Routed instructor query",
        intent=routing.intent.value,
        target_count=len(routing.target_student_ids),
        topic_filter=routing.topic_filter,
    )

    return {"routing": routing, "sources": sources}


def decide_path(state: ClassroomState) -> str:
    """Conditional edge: decide which synthesis path to take."""
    routing = state["routing"]
    if routing.intent == QueryIntent.META:
        return "synthesize_meta"
    if routing.intent == QueryIntent.TOPIC_SPECIFIC and routing.topic_filter:
        return "find_topic_students"
    return "load_mastery"


async def find_topic_students(state: ClassroomState) -> dict:
    """Find students who have mastery data for the topic concept."""
    db = state["_db"]
    qdrant = state["_qdrant"]
    claude = state["_claude"]
    agent = ClassroomAgent(db, qdrant, claude)

    routing = state["routing"]
    context = state["context"]

    topic_ids = await agent._find_topic_students(state["course_id"], routing.topic_filter)
    if topic_ids:
        roster_by_id = {s["id"]: s for s in context.student_roster}
        routing.target_student_ids = topic_ids
        routing.target_student_names = [
            roster_by_id[sid]["name"] for sid in topic_ids if sid in roster_by_id
        ]

    sources = list(state.get("sources", []))
    filters = state.get("source_filters", {})
    if filters.get("mastery", True):
        sources.append(
            SourceRef(
                type="concept_mastery",
                label=f"Concept filter: {routing.topic_filter}",
                detail=f"{len(routing.target_student_ids)} students matched",
            )
        )

    return {"routing": routing, "sources": sources}


async def load_mastery(state: ClassroomState) -> dict:
    """Batch-load concept mastery for target students."""
    filters = state.get("source_filters", {})
    if not filters.get("mastery", True):
        return {"mastery_by_student": {}}

    db = state["_db"]
    qdrant = state["_qdrant"]
    claude = state["_claude"]
    agent = ClassroomAgent(db, qdrant, claude)

    routing = state["routing"]
    mastery = await agent._load_student_mastery(state["course_id"], routing.target_student_ids)
    return {"mastery_by_student": mastery}


def build_summaries(state: ClassroomState) -> dict:
    """Build student summaries from structured data — no LLM."""
    agent_stub = ClassroomAgent.__new__(ClassroomAgent)
    summaries = agent_stub._build_summaries(
        state["routing"],
        state["context"],
        state.get("mastery_by_student", {}),
    )

    # Track per-student sources
    filters = state.get("source_filters", {})
    sources = list(state.get("sources", []))
    context = state["context"]
    roster_by_id = {s["id"]: s for s in context.student_roster}

    for s in summaries:
        roster_entry = roster_by_id.get(s.student_id)
        profile = roster_entry["profile"] if roster_entry else None
        parts: list[str] = []
        if filters.get("profiles", True) and profile:
            parts.append("profile")
        if filters.get("mastery", True) and s.concept_mastery:
            parts.append(f"{len(s.concept_mastery)} concepts")
        sources.append(
            SourceRef(
                type="student_profile",
                label=", ".join(parts) if parts else "enrollment only",
                student_name=s.student_name,
            )
        )

    return {"summaries": summaries, "sources": sources}


async def synthesize(state: ClassroomState) -> dict:
    """LLM synthesis of student summaries into instructor-friendly answer."""
    db = state["_db"]
    qdrant = state["_qdrant"]
    claude = state["_claude"]
    agent = ClassroomAgent(db, qdrant, claude)

    response = await agent._synthesize(
        state["question"],
        state["routing"],
        state["summaries"],
        state["context"],
        state.get("history", []),
        state.get("sources"),
        integration_instructions=state.get("integration_instructions", ""),
    )
    return {"answer": response.text, "widgets": response.widgets, "sources": response.sources}


async def synthesize_meta(state: ClassroomState) -> dict:
    """LLM synthesis for aggregate/meta questions."""
    db = state["_db"]
    qdrant = state["_qdrant"]
    claude = state["_claude"]
    agent = ClassroomAgent(db, qdrant, claude)

    filters = state.get("source_filters", {})
    sources = list(state.get("sources", []))

    if filters.get("profiles", True):
        sources.append(
            SourceRef(
                type="student_profile",
                label="Aggregate engagement & confusion scores",
            )
        )
    if filters.get("mastery", True) and state["context"].concept_overview:
        sources.append(
            SourceRef(
                type="concept_mastery",
                label=f"Top {len(state['context'].concept_overview)} concepts by struggle count",
            )
        )

    response = await agent._answer_meta(
        state["question"],
        state["context"],
        state.get("history", []),
        sources,
        integration_instructions=state.get("integration_instructions", ""),
    )
    return {"answer": response.text, "widgets": response.widgets, "sources": response.sources}


def build_widgets(state: ClassroomState) -> dict:
    """Build widget data from already-loaded context (no-op if synthesize already built them)."""
    # Widgets are already built in synthesize/synthesize_meta via ClassroomAgent internals
    return {}


# ── Build the graph ──


def build_classroom_graph() -> StateGraph:
    """Build the LangGraph classroom agent graph."""
    graph = StateGraph(ClassroomState)

    # Register nodes
    graph.add_node("load_classroom", load_classroom)
    graph.add_node("route_intent", route_intent)
    graph.add_node("find_topic_students", find_topic_students)
    graph.add_node("load_mastery", load_mastery)
    graph.add_node("build_summaries", build_summaries)
    graph.add_node("synthesize", synthesize)
    graph.add_node("synthesize_meta", synthesize_meta)

    # Edges
    graph.add_edge(START, "load_classroom")
    graph.add_edge("load_classroom", "route_intent")
    graph.add_conditional_edges(
        "route_intent",
        decide_path,
        {
            "synthesize_meta": "synthesize_meta",
            "find_topic_students": "find_topic_students",
            "load_mastery": "load_mastery",
        },
    )
    graph.add_edge("find_topic_students", "load_mastery")
    graph.add_edge("load_mastery", "build_summaries")
    graph.add_edge("build_summaries", "synthesize")
    graph.add_edge("synthesize", END)
    graph.add_edge("synthesize_meta", END)

    return graph


# Compile once
_classroom_graph = build_classroom_graph().compile()


async def run_classroom_graph(
    *,
    db: AsyncSession,
    qdrant: QdrantStore,
    claude: ClaudeClient,
    course_id: str,
    question: str,
    history: list[dict[str, str]],
    source_filters: dict[str, bool] | None = None,
    integration_instructions: str = "",
) -> ClassroomResponse:
    """Run the classroom graph and return a ClassroomResponse.

    This replaces ClassroomAgent.answer() with the same behavior
    but using LangGraph for state management and observability.
    """
    initial_state: dict[str, Any] = {
        "course_id": course_id,
        "question": question,
        "history": history,
        "source_filters": source_filters or {},
        "integration_instructions": integration_instructions,
        "_db": db,
        "_qdrant": qdrant,
        "_claude": claude,
    }

    final_state = await _classroom_graph.ainvoke(initial_state)

    return ClassroomResponse(
        text=final_state.get("answer", ""),
        widgets=final_state.get("widgets", []),
        sources=final_state.get("sources", []),
    )
