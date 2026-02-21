"""Tests for contextual bandit: StrategyContext bucketing and context-aware UCB1."""

import math

import pytest

from docere.core.improvement.strategy_archive import (
    MIN_CONTEXT_OBS,
    StrategyArchive,
    StrategyContext,
)


# ── StrategyContext bucketing ──


class TestStrategyContext:
    def test_from_profile_low_confusion(self):
        ctx = StrategyContext.from_profile(0.1, 10, 0.5)
        assert ctx.confusion_level == "low"

    def test_from_profile_mid_confusion(self):
        ctx = StrategyContext.from_profile(0.45, 10, 0.5)
        assert ctx.confusion_level == "mid"

    def test_from_profile_high_confusion(self):
        ctx = StrategyContext.from_profile(0.7, 10, 0.5)
        assert ctx.confusion_level == "high"

    def test_from_profile_new_student(self):
        ctx = StrategyContext.from_profile(0.5, 3, 0.5)
        assert ctx.experience_level == "new"

    def test_from_profile_regular_student(self):
        ctx = StrategyContext.from_profile(0.5, 12, 0.5)
        assert ctx.experience_level == "regular"

    def test_from_profile_experienced_student(self):
        ctx = StrategyContext.from_profile(0.5, 25, 0.5)
        assert ctx.experience_level == "experienced"

    def test_from_profile_poor_quality(self):
        ctx = StrategyContext.from_profile(0.5, 10, 0.2)
        assert ctx.quality_level == "poor"

    def test_from_profile_average_quality(self):
        ctx = StrategyContext.from_profile(0.5, 10, 0.55)
        assert ctx.quality_level == "average"

    def test_from_profile_good_quality(self):
        ctx = StrategyContext.from_profile(0.5, 10, 0.8)
        assert ctx.quality_level == "good"

    def test_key_format(self):
        ctx = StrategyContext.from_profile(0.7, 3, 0.3)
        assert ctx.key == "high:new:poor"

    def test_key_all_combinations(self):
        """All boundary combinations produce valid keys."""
        test_cases = [
            (0.0, 0, 0.0, "low:new:poor"),
            (0.29, 4, 0.39, "low:new:poor"),
            (0.3, 5, 0.4, "mid:regular:average"),
            (0.59, 19, 0.69, "mid:regular:average"),
            (0.6, 20, 0.7, "high:experienced:good"),
            (1.0, 100, 1.0, "high:experienced:good"),
        ]
        for confusion, interactions, score, expected_key in test_cases:
            ctx = StrategyContext.from_profile(confusion, interactions, score)
            assert ctx.key == expected_key, (
                f"Failed for confusion={confusion}, interactions={interactions}, "
                f"score={score}: got {ctx.key}, expected {expected_key}"
            )

    def test_context_reconstructible_from_key(self):
        """Context can be reconstructed from its key string."""
        ctx = StrategyContext.from_profile(0.7, 3, 0.3)
        parts = ctx.key.split(":")
        reconstructed = StrategyContext(*parts)
        assert reconstructed.key == ctx.key


# ── UCB1 context-aware scoring ──


class TestContextAwareUCB1:
    """Test the _ucb1_score method with context."""

    def _make_strategy(self, total_uses, avg_score, applicable_contexts=None):
        """Create a mock strategy object."""
        from unittest.mock import MagicMock
        s = MagicMock()
        s.total_uses = total_uses
        s.avg_score = avg_score
        s.applicable_contexts = applicable_contexts or {}
        return s

    def _archive(self):
        """Create a StrategyArchive with a mock db."""
        from unittest.mock import MagicMock
        return StrategyArchive(db=MagicMock())

    def test_untried_strategy_gets_infinity(self):
        archive = self._archive()
        s = self._make_strategy(0, None)
        score = archive._ucb1_score(s, total_uses=100)
        assert score == float("inf")

    def test_global_fallback_when_no_context(self):
        archive = self._archive()
        s = self._make_strategy(10, 0.7)
        score_no_ctx = archive._ucb1_score(s, total_uses=100, context_key=None)
        # Should use global stats
        expected = 0.7 + math.sqrt(2 * math.log(100) / 10)
        assert score_no_ctx == pytest.approx(expected)

    def test_global_fallback_when_context_insufficient(self):
        """Falls back to global when context bucket has < MIN_CONTEXT_OBS observations."""
        archive = self._archive()
        s = self._make_strategy(10, 0.7, {
            "context_stats": {
                "high:new:poor": {"total_uses": MIN_CONTEXT_OBS - 1, "avg_score": 0.9}
            }
        })
        score = archive._ucb1_score(s, total_uses=100, context_key="high:new:poor")
        expected_global = 0.7 + math.sqrt(2 * math.log(100) / 10)
        assert score == pytest.approx(expected_global)

    def test_context_stats_used_when_sufficient(self):
        """Uses context-specific stats when bucket has >= MIN_CONTEXT_OBS."""
        archive = self._archive()
        s = self._make_strategy(50, 0.5, {
            "context_stats": {
                "high:new:poor": {"total_uses": 10, "avg_score": 0.8}
            }
        })
        score = archive._ucb1_score(s, total_uses=100, context_key="high:new:poor")
        expected_ctx = 0.8 + math.sqrt(2 * math.log(100) / 10)
        expected_global = 0.5 + math.sqrt(2 * math.log(100) / 50)
        assert score == pytest.approx(expected_ctx)
        assert score != pytest.approx(expected_global)

    def test_context_beats_global_when_better(self):
        """Strategy with bad global but good context score should win in context."""
        archive = self._archive()

        # Strategy A: good global, bad in context
        a = self._make_strategy(50, 0.7, {
            "context_stats": {
                "high:new:poor": {"total_uses": 10, "avg_score": 0.3}
            }
        })
        # Strategy B: bad global, good in context
        b = self._make_strategy(30, 0.4, {
            "context_stats": {
                "high:new:poor": {"total_uses": 8, "avg_score": 0.85}
            }
        })

        total = 100
        score_a = archive._ucb1_score(a, total, "high:new:poor")
        score_b = archive._ucb1_score(b, total, "high:new:poor")

        # B should win in this context despite worse global score
        assert score_b > score_a

    def test_unknown_context_key_falls_back(self):
        """Context key not in stats → falls back to global."""
        archive = self._archive()
        s = self._make_strategy(10, 0.7, {
            "context_stats": {
                "low:experienced:good": {"total_uses": 20, "avg_score": 0.9}
            }
        })
        score = archive._ucb1_score(s, total_uses=100, context_key="high:new:poor")
        expected_global = 0.7 + math.sqrt(2 * math.log(100) / 10)
        assert score == pytest.approx(expected_global)
