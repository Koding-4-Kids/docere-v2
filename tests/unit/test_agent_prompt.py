"""Tests for agent system prompt building and score-based adaptation."""

from unittest.mock import MagicMock

import pytest

from docere.core.agent import BASE_SYSTEM_PROMPT, TutoringAgent
from docere.core.memory.memory_layer import MemoryContext


def _make_profile(avg_interaction_score=0.5, avg_confusion=0.3,
                  engagement_level="medium", total_interactions=10):
    """Create a mock StudentProfile."""
    p = MagicMock()
    p.avg_interaction_score = avg_interaction_score
    p.avg_confusion_score = avg_confusion
    p.engagement_level = engagement_level
    p.total_interactions = total_interactions
    return p


def _make_agent():
    """Create a TutoringAgent with mocked deps (only need _build_system_prompt)."""
    agent = object.__new__(TutoringAgent)
    return agent


def _empty_memory():
    return MemoryContext(
        teacher_context="Some course material",
        student_profile="",
        total_tokens=10,
    )


class TestBuildSystemPrompt:
    def test_base_prompt_always_included(self):
        agent = _make_agent()
        prompt = agent._build_system_prompt(_empty_memory(), strategy=None)
        assert BASE_SYSTEM_PROMPT in prompt

    def test_strategy_prompt_injected(self):
        agent = _make_agent()
        strategy = MagicMock()
        strategy.prompt_template = "Use Socratic questioning."
        prompt = agent._build_system_prompt(_empty_memory(), strategy)
        assert "Teaching Strategy" in prompt
        assert "Socratic questioning" in prompt

    def test_no_strategy_section_when_none(self):
        agent = _make_agent()
        prompt = agent._build_system_prompt(_empty_memory(), strategy=None)
        assert "Teaching Strategy" not in prompt

    def test_assignment_context_included(self):
        agent = _make_agent()
        assignment = MagicMock()
        assignment.title = "Recursion Homework"
        assignment.due_at = None
        assignment.description = "Implement factorial"
        assignment.points_possible = 100
        prompt = agent._build_system_prompt(_empty_memory(), strategy=None, assignment=assignment)
        assert "Recursion Homework" in prompt
        assert "Implement factorial" in prompt

    def test_no_materials_note_when_empty(self):
        agent = _make_agent()
        empty = MemoryContext(teacher_context="", student_profile="")
        prompt = agent._build_system_prompt(empty, strategy=None)
        assert "No course materials" in prompt

    def test_adaptation_poor_scores(self):
        """Low interaction score triggers adaptation note."""
        agent = _make_agent()
        profile = _make_profile(avg_interaction_score=0.3, total_interactions=5)
        prompt = agent._build_system_prompt(
            _empty_memory(), strategy=None, profile=profile
        )
        assert "Adaptation Notes" in prompt
        assert "different angle" in prompt

    def test_adaptation_high_confusion_low_engagement(self):
        """High confusion + non-high engagement triggers concrete examples note."""
        agent = _make_agent()
        profile = _make_profile(avg_confusion=0.7, engagement_level="low")
        prompt = agent._build_system_prompt(
            _empty_memory(), strategy=None, profile=profile
        )
        assert "Adaptation Notes" in prompt
        assert "concrete examples" in prompt

    def test_no_adaptation_when_scores_good(self):
        """Good scores → no adaptation section."""
        agent = _make_agent()
        profile = _make_profile(avg_interaction_score=0.8, avg_confusion=0.2)
        prompt = agent._build_system_prompt(
            _empty_memory(), strategy=None, profile=profile
        )
        assert "Adaptation Notes" not in prompt

    def test_no_adaptation_when_too_few_interactions(self):
        """Low score but < 3 interactions → don't adapt yet (not enough data)."""
        agent = _make_agent()
        profile = _make_profile(avg_interaction_score=0.2, total_interactions=2)
        prompt = agent._build_system_prompt(
            _empty_memory(), strategy=None, profile=profile
        )
        # Should NOT trigger the poor-score adaptation (need >= 3 interactions)
        assert "different angle" not in prompt

    def test_no_adaptation_when_no_profile(self):
        """No profile → no adaptation section."""
        agent = _make_agent()
        prompt = agent._build_system_prompt(
            _empty_memory(), strategy=None, profile=None
        )
        assert "Adaptation Notes" not in prompt

    def test_high_confusion_but_high_engagement_no_adaptation(self):
        """High confusion but high engagement → student is trying, don't over-simplify."""
        agent = _make_agent()
        profile = _make_profile(avg_confusion=0.7, engagement_level="high")
        prompt = agent._build_system_prompt(
            _empty_memory(), strategy=None, profile=profile
        )
        assert "concrete examples" not in prompt
