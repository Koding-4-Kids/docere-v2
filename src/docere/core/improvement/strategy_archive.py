"""Strategy archive: maintains and selects teaching strategies using contextual UCB1 bandit.

Seed strategies:
- Socratic Questioning: Ask guiding questions, never give answers directly
- Analogy-First: Begin with real-world analogies before formal concepts
- Scaffolded Hints: 3-level hints (concept → example → walkthrough)
- Error-Focused: Focus on WHY errors happen (common misconceptions)
- Minimal Intervention: Shortest possible hint, let student struggle productively

Context-aware selection:
  Strategy selection is bucketed by student context (confusion × experience × quality).
  Each strategy accumulates per-bucket UCB1 stats in its applicable_contexts JSONB.
  Falls back to global stats when a bucket has fewer than MIN_CONTEXT_OBS observations.
"""

import math
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from docere.models.strategy import Strategy as StrategyModel
from docere.models.strategy import StrategyScore

logger = structlog.get_logger()

# Minimum observations in a context bucket before trusting its stats
MIN_CONTEXT_OBS = 3

_Z = 1.96  # 95% confidence


def _wilson_ci_half_width(p: float, n: int) -> float:
    """Wilson score interval half-width for a proportion p with n observations."""
    if n < 1:
        return 1.0
    z2 = _Z * _Z
    denom = 1 + z2 / n
    spread = _Z * math.sqrt((p * (1 - p) + z2 / (4 * n)) / n) / denom
    return spread


@dataclass
class StrategyContext:
    """Student context for contextual bandit strategy selection."""

    confusion_level: str  # "low", "mid", "high"
    experience_level: str  # "new", "regular", "experienced"
    quality_level: str  # "poor", "average", "good"

    @staticmethod
    def from_profile(
        avg_confusion: float,
        total_interactions: int,
        avg_interaction_score: float,
    ) -> "StrategyContext":
        """Build context buckets from StudentProfile data."""
        confusion = "low" if avg_confusion < 0.3 else "mid" if avg_confusion < 0.6 else "high"
        experience = (
            "new"
            if total_interactions < 5
            else "regular"
            if total_interactions < 20
            else "experienced"
        )
        quality = (
            "poor"
            if avg_interaction_score < 0.4
            else "average"
            if avg_interaction_score < 0.7
            else "good"
        )
        return StrategyContext(confusion, experience, quality)

    @property
    def key(self) -> str:
        return f"{self.confusion_level}:{self.experience_level}:{self.quality_level}"


SEED_STRATEGIES = [
    {
        "name": "Socratic Questioning",
        "description": (
            "Guide students through discovery by asking questions rather than providing answers."
        ),
        "strategy_type": "socratic",
        "prompt_template": (
            "You are a Socratic tutor. NEVER give the answer directly. Instead:\n"
            "1. Ask a clarifying question about what the student already knows\n"
            "2. Guide them to discover the answer through a chain of questions\n"
            "3. If they're stuck after 3 questions, give a targeted hint (not the answer)\n"
            "4. Celebrate when they arrive at the answer themselves"
        ),
        "is_baseline": True,
    },
    {
        "name": "Analogy-First",
        "description": "Begin with real-world analogies before introducing formal concepts.",
        "strategy_type": "analogy",
        "prompt_template": (
            "You are a tutor who teaches through analogies. For every concept:\n"
            "1. Start with a real-world analogy the student can relate to\n"
            "2. Map the analogy to the technical concept step by step\n"
            "3. Then introduce the formal definition/syntax\n"
            "4. Check understanding by asking them to extend the analogy"
        ),
        "is_baseline": True,
    },
    {
        "name": "Scaffolded Hints",
        "description": "Provide 3-level progressive hints: concept → example → walkthrough.",
        "strategy_type": "scaffolded",
        "prompt_template": (
            "You are a tutor who provides scaffolded support. When a student asks for help:\n"
            "1. Level 1 (concept hint): Name the relevant concept "
            "and point them in the right direction\n"
            "2. Level 2 (example hint): Only if they ask again, show a similar worked example\n"
            "3. Level 3 (walkthrough): Only if still stuck, walk through their specific problem\n"
            "Always start at Level 1. Only escalate when the student explicitly asks for more help."
        ),
        "is_baseline": True,
    },
    {
        "name": "Error-Focused",
        "description": "Focus on WHY errors happen and common misconceptions.",
        "strategy_type": "error_focused",
        "prompt_template": (
            "You are a tutor who focuses on errors and misconceptions. When helping:\n"
            "1. First, identify the specific misconception or error in the student's thinking\n"
            '2. Explain WHY that error is common ("Many students think X because...")\n'
            "3. Show the contrast between the misconception and the correct understanding\n"
            "4. Give a test case that exposes the difference"
        ),
        "is_baseline": True,
    },
    {
        "name": "Minimal Intervention",
        "description": "Provide the shortest possible hint to let students struggle productively.",
        "strategy_type": "minimal",
        "prompt_template": (
            "You are a minimalist tutor. Your goal is productive struggle:\n"
            "1. Give the SHORTEST possible hint (one sentence max)\n"
            "2. Wait for the student to try before giving more\n"
            "3. Only elaborate if they explicitly ask\n"
            "4. Encourage them to try and fail - that's learning\n"
            "Less help = more learning. Keep responses under 3 sentences."
        ),
        "is_baseline": True,
    },
]


class StrategyArchive:
    """Archive of teaching strategies with UCB1 bandit selection."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def seed_strategies(self) -> int:
        """Insert seed strategies if the archive is empty."""
        count_result = await self.db.execute(select(func.count(StrategyModel.id)))
        count = count_result.scalar_one()
        if count > 0:
            return 0

        for s in SEED_STRATEGIES:
            self.db.add(StrategyModel(**s))

        await self.db.flush()
        logger.info("Seeded strategies", count=len(SEED_STRATEGIES))
        return len(SEED_STRATEGIES)

    async def select_strategy(
        self,
        study_group: str | None,
        context: StrategyContext | None = None,
    ) -> StrategyModel | None:
        """Select a teaching strategy using contextual UCB1 multi-armed bandit.

        For control/treatment_a groups, returns None (no strategy augmentation).
        For treatment_full, uses UCB1 to balance exploration vs exploitation.
        When context is provided, uses per-context stats if enough data exists,
        otherwise falls back to global stats.
        """
        if study_group in ("control", "treatment_a"):
            return None

        result = await self.db.execute(
            select(StrategyModel).where(StrategyModel.is_active.is_(True))
        )
        strategies = result.scalars().all()

        if not strategies:
            return None

        total_uses = sum(s.total_uses for s in strategies) or 1
        context_key = context.key if context else None

        # UCB1 selection (context-aware when possible)
        best_strategy = None
        best_score = -1.0

        for strategy in strategies:
            score = self._ucb1_score(strategy, total_uses, context_key)
            if score > best_score:
                best_score = score
                best_strategy = strategy

        if best_strategy:
            best_strategy.total_uses += 1
            best_strategy.last_used_at = datetime.now(UTC)
            await self.db.flush()

        logger.info(
            "Strategy selected",
            strategy=best_strategy.name if best_strategy else None,
            context_key=context_key,
            ucb1_score=f"{best_score:.3f}" if best_score != float("inf") else "inf",
        )

        return best_strategy

    def _ucb1_score(
        self,
        strategy: StrategyModel,
        total_uses: int,
        context_key: str | None = None,
    ) -> float:
        """Calculate UCB1 score, using context-specific stats when available."""
        # Try context-specific stats first
        if context_key:
            ctx_stats = (
                (strategy.applicable_contexts or {}).get("context_stats", {}).get(context_key)
            )
            if ctx_stats and ctx_stats.get("total_uses", 0) >= MIN_CONTEXT_OBS:
                exploitation = ctx_stats["avg_score"]
                exploration = math.sqrt(2 * math.log(total_uses) / ctx_stats["total_uses"])
                return float(exploitation) + exploration

        # Fall back to global stats
        if strategy.total_uses == 0:
            return float("inf")
        exploitation = strategy.avg_score or 0.0
        exploration = math.sqrt(2 * math.log(total_uses) / strategy.total_uses)
        return exploitation + exploration

    async def record_outcome(
        self,
        strategy_id: str,
        conversation_id: str,
        score: float,
        interaction_score_id: str | None = None,
        context_metadata: dict[str, Any] | None = None,
        context: StrategyContext | None = None,
    ) -> None:
        """Record an interaction outcome for a strategy.

        Updates both global stats and context-specific stats (if context provided).
        """
        self.db.add(
            StrategyScore(
                strategy_id=strategy_id,
                conversation_id=conversation_id,
                interaction_score_id=interaction_score_id,
                score=score,
                context_metadata=context_metadata or {},
            )
        )

        # Update global running average
        result = await self.db.execute(select(StrategyModel).where(StrategyModel.id == strategy_id))
        strategy = result.scalar_one_or_none()
        if strategy:
            n = strategy.total_uses or 1
            old_avg = strategy.avg_score or 0.0
            strategy.avg_score = (old_avg * (n - 1) + score) / n
            if score >= 0.6:
                old_success = strategy.success_rate or 0.0
                strategy.success_rate = (old_success * (n - 1) + 1.0) / n
            else:
                old_success = strategy.success_rate or 0.0
                strategy.success_rate = (old_success * (n - 1)) / n

            # Wilson score interval half-width (95% CI)
            strategy.confidence_interval = _wilson_ci_half_width(strategy.success_rate or 0.0, n)

            # Update context-specific stats
            if context:
                ctx_key = context.key
                applicable = strategy.applicable_contexts or {}
                ctx_stats = applicable.setdefault("context_stats", {})
                bucket = ctx_stats.get(ctx_key, {"total_uses": 0, "avg_score": 0.0})
                bn = bucket["total_uses"]
                bucket["avg_score"] = (bucket["avg_score"] * bn + score) / (bn + 1)
                bucket["total_uses"] = bn + 1
                ctx_stats[ctx_key] = bucket
                strategy.applicable_contexts = applicable

                logger.debug(
                    "Context stats updated",
                    strategy=strategy.name,
                    context_key=ctx_key,
                    bucket_uses=bucket["total_uses"],
                    bucket_avg=f"{bucket['avg_score']:.3f}",
                )

        await self.db.flush()

    async def incorporate_grade_signal(
        self,
        interaction_score_id: str,
        grade_percentage: float,
    ) -> None:
        """Blend a grade signal into the strategy score that produced this interaction."""
        result = await self.db.execute(
            select(StrategyScore).where(StrategyScore.interaction_score_id == interaction_score_id)
        )
        strategy_score = result.scalar_one_or_none()
        if not strategy_score:
            return

        # Blend: 70% original composite, 30% grade signal
        old_score = strategy_score.score
        blended = old_score * 0.7 + grade_percentage * 0.3
        strategy_score.score = blended

        # Adjust parent strategy's avg_score by the delta
        delta = blended - old_score
        strategy_result = await self.db.execute(
            select(StrategyModel).where(StrategyModel.id == strategy_score.strategy_id)
        )
        strategy = strategy_result.scalar_one_or_none()
        if strategy and strategy.total_uses:
            strategy.avg_score = (strategy.avg_score or 0.0) + delta / strategy.total_uses
            strategy.confidence_interval = _wilson_ci_half_width(
                strategy.success_rate or 0.0, strategy.total_uses
            )

        await self.db.flush()
