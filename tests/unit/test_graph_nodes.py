"""Tests for individual LangGraph node functions."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestParseOutput:
    """Test the parse_output node that extracts artifacts/actions/widgets."""

    async def test_plain_text_no_artifacts(self):
        from docere.core.graphs.nodes.parsing import parse_output

        state = {
            "response_text": "Recursion is when a function calls itself.",
            "message": "explain recursion",
        }
        result = parse_output(state)
        assert result["chat_text"] == "Recursion is when a function calls itself."
        assert result["artifact"] is None
        assert result["action"] is None
        assert result["widgets"] == []

    async def test_extracts_artifact_block(self):
        from docere.core.graphs.nodes.parsing import parse_output

        response = (
            "Here are some flashcards:\n\n"
            "```artifact\n"
            '{"type": "flashcards", "content": "test"}\n'
            "```\n"
        )
        state = {
            "response_text": response,
            "message": "make flashcards",
        }
        result = parse_output(state)
        assert result["artifact"] is not None
        assert result["artifact"]["type"] == "flashcards"
        # Chat text should have the artifact block removed
        assert "```artifact" not in result["chat_text"]

    async def test_extracts_action_block(self):
        from docere.core.graphs.nodes.parsing import parse_output

        response = (
            "Let me suggest a study group meeting.\n\n"
            "```action\n"
            '{"type": "meeting_suggestion", "reason": "Study session", "concepts": []}\n'
            "```\n"
        )
        state = {
            "response_text": response,
            "message": "can we meet?",
        }
        result = parse_output(state)
        assert result["action"] is not None
        assert result["action"]["type"] == "meeting_suggestion"
        assert "```action" not in result["chat_text"]


class TestBuildPrompt:
    """Test the build_prompt node assembles system prompts correctly."""

    @staticmethod
    def _make_memory_context():
        """Create a mock MemoryContext with to_system_context()."""
        ctx = MagicMock()
        ctx.to_system_context.return_value = ""
        ctx.total_tokens = 0
        ctx.study_materials = []
        return ctx

    async def test_base_prompt_always_present(self):
        from docere.core.graphs.nodes.llm import build_prompt
        from docere.core.agent import BASE_SYSTEM_PROMPT

        state = {
            "student_id": str(uuid.uuid4()),
            "course_id": str(uuid.uuid4()),
            "memory_context": self._make_memory_context(),
            "student_profile": None,
            "assignment": None,
            "strategy": None,
            "strategy_context": None,
            "message": "hello",
        }
        result = build_prompt(state)
        assert "system_prompt" in result
        assert BASE_SYSTEM_PROMPT[:50] in result["system_prompt"]

    async def test_strategy_template_injected(self):
        from docere.core.graphs.nodes.llm import build_prompt

        mock_strategy = MagicMock()
        mock_strategy.name = "Socratic"
        mock_strategy.prompt_template = "Ask guiding questions."

        state = {
            "student_id": str(uuid.uuid4()),
            "course_id": str(uuid.uuid4()),
            "memory_context": self._make_memory_context(),
            "student_profile": None,
            "assignment": None,
            "strategy": mock_strategy,
            "strategy_context": None,
            "message": "hello",
        }
        result = build_prompt(state)
        assert "Ask guiding questions" in result["system_prompt"]

    async def test_assignment_context_injected(self):
        from docere.core.graphs.nodes.llm import build_prompt

        mock_assignment = MagicMock()
        mock_assignment.title = "Homework 3"
        mock_assignment.description = "Binary trees"
        mock_assignment.due_at = datetime(2026, 3, 15, tzinfo=timezone.utc)
        mock_assignment.points_possible = 100.0

        state = {
            "student_id": str(uuid.uuid4()),
            "course_id": str(uuid.uuid4()),
            "memory_context": self._make_memory_context(),
            "student_profile": None,
            "assignment": mock_assignment,
            "strategy": None,
            "strategy_context": None,
            "message": "hello",
        }
        result = build_prompt(state)
        assert "Homework 3" in result["system_prompt"]


class TestSelectStrategy:
    """Test strategy selection node."""

    async def test_returns_none_for_control_group(self):
        from docere.core.graphs.nodes.strategy import select_strategy

        state = {
            "student_id": str(uuid.uuid4()),
            "course_id": str(uuid.uuid4()),
            "study_group": "control",
            "student_profile": None,
            "_db": MagicMock(),
        }
        result = await select_strategy(state)
        assert result["strategy"] is None
        assert result["strategy_context"] is None
