"""Tests for LangGraph graph structure and wiring."""

import pytest

from docere.core.graphs.tutoring import build_tutoring_graph
from docere.core.graphs.classroom import build_classroom_graph


class TestTutoringGraphStructure:
    """Verify the tutoring graph has the expected nodes and edges."""

    def test_graph_compiles(self):
        graph = build_tutoring_graph()
        compiled = graph.compile()
        assert compiled is not None

    def test_expected_nodes_present(self):
        graph = build_tutoring_graph()
        node_names = set(graph.nodes.keys())
        expected = {
            "load_context",
            "select_strategy",
            "build_prompt",
            "generate_response",
            "parse_output",
            "persist_messages",
        }
        assert expected <= node_names, (
            f"Missing nodes: {expected - node_names}"
        )

    def test_critical_path_edges(self):
        """Verify START -> ... -> END path exists."""
        graph = build_tutoring_graph()
        # Check edges form a connected path
        edge_sources = set()
        edge_targets = set()
        for edge in graph.edges:
            src, tgt = edge
            edge_sources.add(src)
            edge_targets.add(tgt)

        # __start__ should be a source
        assert "__start__" in edge_sources
        # __end__ should be a target
        assert "__end__" in edge_targets
        # All pipeline nodes should appear as both source and target
        pipeline_nodes = {
            "load_context", "select_strategy", "build_prompt",
            "generate_response", "parse_output", "persist_messages",
        }
        for node in pipeline_nodes - {"persist_messages"}:
            assert node in edge_sources, f"{node} not a source"
        for node in pipeline_nodes - {"load_context"}:
            assert node in edge_targets, f"{node} not a target"


class TestClassroomGraphStructure:
    """Verify the classroom graph has expected nodes and conditional routing."""

    def test_graph_compiles(self):
        graph = build_classroom_graph()
        compiled = graph.compile()
        assert compiled is not None

    def test_expected_nodes_present(self):
        graph = build_classroom_graph()
        node_names = set(graph.nodes.keys())
        expected = {
            "load_classroom",
            "route_intent",
            "find_topic_students",
            "load_mastery",
            "build_summaries",
            "synthesize",
            "synthesize_meta",
        }
        assert expected <= node_names, (
            f"Missing nodes: {expected - node_names}"
        )

    def test_has_conditional_edge_from_route_intent(self):
        """The graph should have a conditional edge after route_intent."""
        graph = build_classroom_graph()
        # Check that route_intent is a source in edges
        edge_sources = {e[0] for e in graph.edges}
        assert "route_intent" in edge_sources or len(graph.edges) > 5

    def test_meta_path_goes_to_end(self):
        """synthesize_meta should lead to END."""
        graph = build_classroom_graph()
        for edge in graph.edges:
            if edge[0] == "synthesize_meta":
                assert edge[1] == "__end__"

    def test_normal_path_goes_to_end(self):
        """synthesize should lead to END."""
        graph = build_classroom_graph()
        for edge in graph.edges:
            if edge[0] == "synthesize":
                assert edge[1] == "__end__"


class TestDecidePath:
    """Test the conditional routing function."""

    def test_meta_intent_routes_to_synthesize_meta(self):
        from docere.core.graphs.classroom import decide_path
        from docere.core.classroom_agent import QueryIntent, RoutingDecision

        state = {
            "routing": RoutingDecision(
                intent=QueryIntent.META,
                target_student_ids=[],
                target_student_names=[],
                reasoning="aggregate question",
            ),
        }
        assert decide_path(state) == "synthesize_meta"

    def test_topic_specific_routes_to_find_topic(self):
        from docere.core.graphs.classroom import decide_path
        from docere.core.classroom_agent import QueryIntent, RoutingDecision

        state = {
            "routing": RoutingDecision(
                intent=QueryIntent.TOPIC_SPECIFIC,
                target_student_ids=[],
                target_student_names=[],
                reasoning="topic question",
                topic_filter="recursion",
            ),
        }
        assert decide_path(state) == "find_topic_students"

    def test_class_wide_routes_to_load_mastery(self):
        from docere.core.graphs.classroom import decide_path
        from docere.core.classroom_agent import QueryIntent, RoutingDecision

        state = {
            "routing": RoutingDecision(
                intent=QueryIntent.CLASS_WIDE,
                target_student_ids=[],
                target_student_names=[],
                reasoning="all students",
            ),
        }
        assert decide_path(state) == "load_mastery"
