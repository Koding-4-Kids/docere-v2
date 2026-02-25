"""Tests for StrategyEvolver: mutation, pruning, convergence, and context scoring."""

import json
import math
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from docere.core.improvement.strategy_archive import _wilson_ci_half_width
from docere.core.improvement.strategy_evolver import StrategyEvolver


# ── Helpers ──


def _make_strategy(
    name="Test Strategy",
    avg_score=0.7,
    total_uses=10,
    is_active=True,
    is_baseline=False,
    success_rate=0.6,
    strategy_type="socratic",
    description="A test strategy",
    prompt_template="Ask questions to guide the student.",
    generation=0,
):
    s = MagicMock()
    s.id = uuid.uuid4()
    s.name = name
    s.avg_score = avg_score
    s.total_uses = total_uses
    s.is_active = is_active
    s.is_baseline = is_baseline
    s.success_rate = success_rate
    s.strategy_type = strategy_type
    s.description = description
    s.prompt_template = prompt_template
    s.generation = generation
    return s


def _mock_db_returning(strategies):
    """Create a mock AsyncSession whose execute().scalars().all() returns strategies."""
    db = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = strategies
    db.execute.return_value = result
    return db


def _evolver(db=None, claude=None):
    return StrategyEvolver(
        db=db or AsyncMock(),
        claude=claude or AsyncMock(),
    )


# ── TestEvolve ──


class TestEvolve:
    @pytest.mark.asyncio
    async def test_no_strategies(self):
        """Empty archive returns zero mutations and prunings."""
        db = _mock_db_returning([])
        evolver = _evolver(db=db)
        result = await evolver.evolve()
        assert result["mutations"] == 0
        assert result["pruned"] == 0

    @pytest.mark.asyncio
    async def test_skips_low_usage(self):
        """Strategies with < 5 uses are not mutated."""
        s = _make_strategy(total_uses=3, avg_score=0.9)
        db = _mock_db_returning([s])
        evolver = _evolver(db=db)

        with patch.object(evolver, "_mutate_strategy", new_callable=AsyncMock) as mock_mutate:
            with patch("docere.core.improvement.strategy_evolver.settings") as mock_settings:
                mock_settings.strategy_evolution_top_k = 3
                mock_settings.strategy_min_uses_for_prune = 20
                mock_settings.strategy_prune_score_threshold = 0.3
                result = await evolver.evolve()

        mock_mutate.assert_not_called()
        assert result["mutations"] == 0

    @pytest.mark.asyncio
    async def test_mutates_top_k(self):
        """Top K strategies by avg_score get mutated."""
        strategies = [
            _make_strategy(name="Best", avg_score=0.9, total_uses=10),
            _make_strategy(name="Mid", avg_score=0.6, total_uses=10),
            _make_strategy(name="Worst", avg_score=0.3, total_uses=10),
        ]
        db = _mock_db_returning(strategies)
        evolver = _evolver(db=db)

        mutated = MagicMock()
        mutated.name = "Best v2"

        with patch.object(evolver, "_mutate_strategy", new_callable=AsyncMock, return_value=mutated):
            with patch("docere.core.improvement.strategy_evolver.settings") as mock_settings:
                mock_settings.strategy_evolution_top_k = 1
                mock_settings.strategy_min_uses_for_prune = 20
                mock_settings.strategy_prune_score_threshold = 0.3
                result = await evolver.evolve()

        assert result["mutations"] == 1
        assert "Best v2" in result["mutated_from"]

    @pytest.mark.asyncio
    async def test_prunes_weak(self):
        """Strategies with >= min_uses and avg_score < threshold get deactivated."""
        weak = _make_strategy(name="Weak", avg_score=0.2, total_uses=25, is_baseline=False)
        strong = _make_strategy(name="Strong", avg_score=0.8, total_uses=25, is_baseline=False)
        db = _mock_db_returning([strong, weak])
        evolver = _evolver(db=db)

        with patch.object(evolver, "_mutate_strategy", new_callable=AsyncMock, return_value=None):
            with patch("docere.core.improvement.strategy_evolver.settings") as mock_settings:
                mock_settings.strategy_evolution_top_k = 1
                mock_settings.strategy_min_uses_for_prune = 20
                mock_settings.strategy_prune_score_threshold = 0.3
                result = await evolver.evolve()

        assert result["pruned"] == 1
        assert "Weak" in result["pruned_names"]
        assert weak.is_active is False

    @pytest.mark.asyncio
    async def test_never_prunes_baseline(self):
        """Baseline strategies survive pruning even with terrible scores."""
        baseline = _make_strategy(
            name="Seed", avg_score=0.1, total_uses=50, is_baseline=True
        )
        db = _mock_db_returning([baseline])
        evolver = _evolver(db=db)

        with patch.object(evolver, "_mutate_strategy", new_callable=AsyncMock, return_value=None):
            with patch("docere.core.improvement.strategy_evolver.settings") as mock_settings:
                mock_settings.strategy_evolution_top_k = 1
                mock_settings.strategy_min_uses_for_prune = 20
                mock_settings.strategy_prune_score_threshold = 0.3
                result = await evolver.evolve()

        assert result["pruned"] == 0
        assert baseline.is_active is True


# ── TestMutateStrategy ──


class TestMutateStrategy:
    @pytest.mark.asyncio
    async def test_parses_valid_json(self):
        """Valid Claude JSON response creates a new Strategy with correct lineage."""
        parent = _make_strategy(name="Parent", generation=1, total_uses=10)
        response_json = json.dumps({
            "name": "Parent v2",
            "description": "Improved variant",
            "prompt_template": "completely new and different instructions for tutoring students",
        })

        claude = AsyncMock()
        claude.chat.return_value = response_json

        db = AsyncMock()
        # _is_too_similar needs db.execute to return empty results
        similar_result = MagicMock()
        similar_result.all.return_value = []
        db.execute.return_value = similar_result

        evolver = _evolver(db=db, claude=claude)
        result = await evolver._mutate_strategy(parent)

        assert result is not None
        db.add.assert_called_once()
        added = db.add.call_args[0][0]
        assert added.name == "Parent v2"
        assert added.generation == 2
        assert added.parent_strategy_id == parent.id

    @pytest.mark.asyncio
    async def test_handles_markdown_fences(self):
        """JSON wrapped in ```json blocks still parses."""
        parent = _make_strategy(total_uses=10)
        response = '```json\n{"name": "V2", "description": "Better", "prompt_template": "unique new approach to teaching"}\n```'

        claude = AsyncMock()
        claude.chat.return_value = response

        db = AsyncMock()
        similar_result = MagicMock()
        similar_result.all.return_value = []
        db.execute.return_value = similar_result

        evolver = _evolver(db=db, claude=claude)
        result = await evolver._mutate_strategy(parent)

        assert result is not None

    @pytest.mark.asyncio
    async def test_rejects_too_similar(self):
        """Convergence check rejects mutation with >80% word overlap."""
        parent = _make_strategy(total_uses=10)
        # Return a template that's identical to existing
        response_json = json.dumps({
            "name": "Clone",
            "description": "Same thing",
            "prompt_template": "Ask questions to guide the student.",
        })

        claude = AsyncMock()
        claude.chat.return_value = response_json

        db = AsyncMock()
        # _get_score_contexts returns empty
        score_result = MagicMock()
        score_result.all.return_value = []

        # _is_too_similar returns the existing template
        similar_result = MagicMock()
        similar_result.all.return_value = [
            ("Ask questions to guide the student.",),
        ]

        # First two calls are for _get_score_contexts (best, worst), third is _is_too_similar
        db.execute.side_effect = [score_result, score_result, similar_result]

        evolver = _evolver(db=db, claude=claude)
        result = await evolver._mutate_strategy(parent)

        assert result is None
        db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_bad_json(self):
        """Malformed Claude response returns None without crashing."""
        parent = _make_strategy(total_uses=10)

        claude = AsyncMock()
        claude.chat.return_value = "Sorry, I can't generate that."

        db = AsyncMock()
        score_result = MagicMock()
        score_result.all.return_value = []
        db.execute.return_value = score_result

        evolver = _evolver(db=db, claude=claude)
        result = await evolver._mutate_strategy(parent)

        assert result is None


# ── TestIsTooSimilar ──


class TestIsTooSimilar:
    @pytest.mark.asyncio
    async def test_identical_rejected(self):
        """100% overlap returns True."""
        db = AsyncMock()
        result = MagicMock()
        result.all.return_value = [("hello world foo bar baz",)]
        db.execute.return_value = result

        evolver = _evolver(db=db)
        assert await evolver._is_too_similar("hello world foo bar baz") is True

    @pytest.mark.asyncio
    async def test_different_accepted(self):
        """Completely different content returns False."""
        db = AsyncMock()
        result = MagicMock()
        result.all.return_value = [("alpha beta gamma delta epsilon",)]
        db.execute.return_value = result

        evolver = _evolver(db=db)
        assert await evolver._is_too_similar("one two three four five") is False

    @pytest.mark.asyncio
    async def test_empty_template(self):
        """Empty string returns False."""
        db = AsyncMock()
        evolver = _evolver(db=db)
        assert await evolver._is_too_similar("") is False


# ── TestGetScoreContexts ──


class TestGetScoreContexts:
    @pytest.mark.asyncio
    async def test_returns_rich_context_with_dimensions(self):
        """Context strings include dimension breakdowns from metadata."""
        db = AsyncMock()
        result = MagicMock()
        result.all.return_value = [
            (
                0.85,  # score
                {
                    "concept": "derivatives",
                    "helpfulness": 0.95,
                    "clarity": 0.70,
                    "engagement": 0.85,
                    "understanding_delta": 0.15,
                    "followup_type": "deeper_question",
                },
                "Let's think about the rate of change...",  # msg_content
                "assistant",  # msg_role
            ),
        ]
        db.execute.return_value = result

        evolver = _evolver(db=db)
        contexts = await evolver._get_score_contexts(uuid.uuid4(), best=True)

        assert len(contexts) == 1
        ctx = contexts[0]
        assert "derivatives" in ctx
        assert "Helpfulness: 0.95" in ctx
        assert "Clarity: 0.70" in ctx
        assert "Engagement: 0.85" in ctx
        assert "Understanding delta: +0.15" in ctx
        assert "Followup: deeper_question" in ctx
        assert "Composite: 0.85" in ctx

    @pytest.mark.asyncio
    async def test_handles_missing_metadata(self):
        """Graceful with None/empty context_metadata."""
        db = AsyncMock()
        result = MagicMock()
        result.all.return_value = [
            (0.50, None, None, None),
            (0.40, {}, "Some response", "assistant"),
        ]
        db.execute.return_value = result

        evolver = _evolver(db=db)
        contexts = await evolver._get_score_contexts(uuid.uuid4(), best=False)

        assert len(contexts) == 2
        assert "Composite: 0.50" in contexts[0]
        assert "Composite: 0.40" in contexts[1]
        assert "Some response" in contexts[1]


# ── TestWilsonCI ──


class TestWilsonCI:
    def test_perfect_rate_small_n(self):
        """p=1.0 with small n still produces a positive CI."""
        ci = _wilson_ci_half_width(1.0, 5)
        assert ci > 0
        assert ci < 1.0

    def test_zero_rate(self):
        """p=0.0 produces a positive CI (uncertainty about true rate)."""
        ci = _wilson_ci_half_width(0.0, 10)
        assert ci > 0

    def test_ci_shrinks_with_more_data(self):
        """CI at n=100 should be smaller than CI at n=5 for same p."""
        ci_small = _wilson_ci_half_width(0.6, 5)
        ci_large = _wilson_ci_half_width(0.6, 100)
        assert ci_large < ci_small

    def test_ci_at_n_zero(self):
        """n=0 returns maximum uncertainty."""
        ci = _wilson_ci_half_width(0.5, 0)
        assert ci == 1.0

    def test_known_value(self):
        """Verify against hand-calculated Wilson CI for p=0.5, n=20."""
        p, n = 0.5, 20
        z = 1.96
        z2 = z * z
        denom = 1 + z2 / n
        expected = z * math.sqrt((p * (1 - p) + z2 / (4 * n)) / n) / denom
        assert _wilson_ci_half_width(p, n) == pytest.approx(expected)
