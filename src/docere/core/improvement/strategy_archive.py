"""Strategy archive: maintains and selects teaching strategies using UCB1 bandit.

Seed strategies:
- Socratic Questioning: Ask guiding questions, never give answers directly
- Analogy-First: Begin with real-world analogies before formal concepts
- Scaffolded Hints: 3-level hints (concept → example → walkthrough)
- Error-Focused: Focus on WHY errors happen (common misconceptions)
- Minimal Intervention: Shortest possible hint, let student struggle productively
"""

import math
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from docere.models.strategy import Strategy as StrategyModel, StrategyScore

logger = structlog.get_logger()

SEED_STRATEGIES = [
    {
        "name": "Socratic Questioning",
        "description": "Guide students through discovery by asking questions rather than providing answers.",
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
            "1. Level 1 (concept hint): Name the relevant concept and point them in the right direction\n"
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
            "2. Explain WHY that error is common (\"Many students think X because...\")\n"
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
        count_result = await self.db.execute(
            select(func.count(StrategyModel.id))
        )
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
    ) -> StrategyModel | None:
        """Select a teaching strategy using UCB1 multi-armed bandit.

        For control/treatment_a groups, returns None (no strategy augmentation).
        For treatment_full, uses UCB1 to balance exploration vs exploitation.
        """
        if study_group != "treatment_full":
            return None

        # Fetch all active strategies
        result = await self.db.execute(
            select(StrategyModel).where(StrategyModel.is_active.is_(True))
        )
        strategies = result.scalars().all()

        if not strategies:
            return None

        # Calculate total uses across all strategies
        total_uses = sum(s.total_uses for s in strategies) or 1

        # UCB1 selection
        best_strategy = None
        best_score = -1.0

        for strategy in strategies:
            score = self._ucb1_score(strategy, total_uses)
            if score > best_score:
                best_score = score
                best_strategy = strategy

        if best_strategy:
            best_strategy.total_uses += 1
            best_strategy.last_used_at = datetime.now(timezone.utc)
            await self.db.flush()

        return best_strategy

    def _ucb1_score(self, strategy: StrategyModel, total_uses: int) -> float:
        """Calculate UCB1 score for a strategy."""
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
    ) -> None:
        """Record an interaction outcome for a strategy."""
        self.db.add(
            StrategyScore(
                strategy_id=strategy_id,
                conversation_id=conversation_id,
                interaction_score_id=interaction_score_id,
                score=score,
            )
        )

        # Update running average
        result = await self.db.execute(
            select(StrategyModel).where(StrategyModel.id == strategy_id)
        )
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

        await self.db.flush()
