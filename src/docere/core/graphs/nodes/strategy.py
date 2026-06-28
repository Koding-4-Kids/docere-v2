"""Strategy selection graph node."""

from __future__ import annotations

from typing import Any

import structlog

from docere.core.graphs.state import TutoringState
from docere.core.improvement.strategy_archive import StrategyArchive, StrategyContext

logger = structlog.get_logger()


async def select_strategy(state: TutoringState) -> dict[str, Any]:
    """Select a teaching strategy using the UCB1 bandit."""
    db = state["_db"]
    archive = StrategyArchive(db)

    profile = state.get("student_profile")
    study_group = state.get("study_group")

    strategy_ctx = None
    if profile:
        strategy_ctx = StrategyContext.from_profile(
            avg_confusion=profile.avg_confusion_score,
            total_interactions=profile.total_interactions,
            avg_interaction_score=profile.avg_interaction_score or 0.5,
        )

    strategy = await archive.select_strategy(study_group, context=strategy_ctx)

    return {
        "strategy": strategy,
        "strategy_context": strategy_ctx,
    }
