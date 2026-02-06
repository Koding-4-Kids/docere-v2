"""Strategy archive: maintains and selects teaching strategies using UCB1 bandit.

Seed strategies:
- Socratic Questioning: Ask guiding questions, never give answers directly
- Analogy-First: Begin with real-world analogies before formal concepts
- Scaffolded Hints: 3-level hints (concept → example → walkthrough)
- Error-Focused: Focus on WHY errors happen (common misconceptions)
- Minimal Intervention: Shortest possible hint, let student struggle productively
"""

import math
from dataclasses import dataclass


@dataclass
class Strategy:
    """A teaching strategy with performance tracking."""

    id: str
    name: str
    description: str
    strategy_type: str
    prompt_template: str
    total_uses: int = 0
    avg_score: float = 0.0
    success_rate: float = 0.0
    is_active: bool = True

    @classmethod
    def default(cls) -> "Strategy":
        """Default strategy (no special augmentation)."""
        return cls(
            id="default",
            name="Default",
            description="Standard tutoring with no special strategy augmentation.",
            strategy_type="default",
            prompt_template="",
        )


class StrategyArchive:
    """Archive of teaching strategies with UCB1 bandit selection."""

    async def select_strategy(
        self,
        student_context: dict[str, object],
        concept_context: str,
        study_group: str,
    ) -> Strategy:
        """Select a teaching strategy using UCB1 multi-armed bandit.

        Balances exploitation (use what works) vs exploration (try new strategies).

        UCB1 score = avg_score + sqrt(2 * ln(total_uses) / strategy_uses)

        For control/treatment_a groups, always returns default strategy.
        """
        if study_group != "treatment_full":
            return Strategy.default()

        # TODO: Fetch active strategies, apply UCB1 selection
        raise NotImplementedError

    def _ucb1_score(self, strategy: Strategy, total_uses: int) -> float:
        """Calculate UCB1 score for a strategy."""
        if strategy.total_uses == 0:
            return float("inf")  # Always explore untested strategies
        exploitation = strategy.avg_score
        exploration = math.sqrt(2 * math.log(total_uses) / strategy.total_uses)
        return exploitation + exploration

    async def record_outcome(
        self,
        strategy_id: str,
        conversation_id: str,
        score: float,
        context_metadata: dict[str, object] | None = None,
    ) -> None:
        """Record an interaction outcome for a strategy."""
        # TODO: Insert strategy_score, update strategy avg_score and success_rate
        raise NotImplementedError
