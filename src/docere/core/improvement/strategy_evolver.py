"""Strategy evolution: weekly task that mutates top strategies and prunes weak ones.

Inspired by Darwin Godel Machine's archive-based exploration.

Process:
1. Evaluate all active strategies (avg_score, success_rate, confidence)
2. Take top K performers, generate variants via Claude
3. Prune strategies with >20 uses and avg_score < 0.3
4. Log all evolution events for research
"""

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from docere.config import settings
from docere.integrations.llm.client import ClaudeClient
from docere.models.strategy import Strategy, StrategyScore

logger = structlog.get_logger()

MUTATION_PROMPT = """You are evolving a teaching strategy for an AI tutor.

Current strategy:
- Name: {name}
- Description: {description}
- Prompt template: {prompt_template}
- Average effectiveness score: {avg_score:.2f}
- Success rate: {success_rate:.1%}

Contexts where it performed BEST:
{top_contexts}

Contexts where it performed WORST:
{bottom_contexts}

Generate an improved variant of this strategy. Keep the core approach but refine it
based on what worked and what didn't. The new strategy should be different enough to
be worth testing but similar enough to inherit the parent's strengths.

Respond with a JSON object:
{{"name": "Strategy Name (v2)", "description": "Brief description", "prompt_template": "Full tutoring instructions"}}"""


class StrategyEvolver:
    """Evolves the teaching strategy archive based on outcomes."""

    def __init__(self, db: AsyncSession, claude: ClaudeClient):
        self.db = db
        self.claude = claude

    async def evolve(self) -> dict[str, object]:
        """Run one evolution cycle.

        Returns summary of actions taken (mutations, prunings).
        """
        result = await self.db.execute(
            select(Strategy).where(Strategy.is_active.is_(True))
        )
        strategies = result.scalars().all()

        if not strategies:
            return {"mutations": 0, "pruned": 0, "message": "No active strategies"}

        # Sort by avg_score descending
        scored = sorted(strategies, key=lambda s: s.avg_score or 0, reverse=True)

        # Step 1: Mutate top K performers
        top_k = settings.strategy_evolution_top_k
        mutations = []
        for strategy in scored[:top_k]:
            if (strategy.total_uses or 0) < 5:
                continue  # Not enough data to evolve

            new_strategy = await self._mutate_strategy(strategy)
            if new_strategy:
                mutations.append(new_strategy.name)

        # Step 2: Prune weak strategies
        pruned = []
        min_uses = settings.strategy_min_uses_for_prune
        threshold = settings.strategy_prune_score_threshold

        for strategy in strategies:
            if strategy.is_baseline:
                continue  # Never prune seed strategies
            if (strategy.total_uses or 0) >= min_uses and (strategy.avg_score or 0) < threshold:
                strategy.is_active = False
                pruned.append(strategy.name)
                logger.info(
                    "Pruned strategy",
                    name=strategy.name,
                    uses=strategy.total_uses,
                    avg_score=strategy.avg_score,
                )

        await self.db.flush()

        summary = {
            "mutations": len(mutations),
            "mutated_from": mutations,
            "pruned": len(pruned),
            "pruned_names": pruned,
            "active_count": len([s for s in strategies if s.is_active]),
        }

        logger.info("Strategy evolution complete", **summary)
        return summary

    async def _mutate_strategy(self, strategy: Strategy) -> Strategy | None:
        """Generate a strategy variant via Claude."""
        # Get top and bottom scoring contexts
        top_contexts = await self._get_score_contexts(strategy.id, best=True)
        bottom_contexts = await self._get_score_contexts(strategy.id, best=False)

        top_str = "\n".join(f"- {c}" for c in top_contexts) or "No data yet"
        bottom_str = "\n".join(f"- {c}" for c in bottom_contexts) or "No data yet"

        prompt = MUTATION_PROMPT.format(
            name=strategy.name,
            description=strategy.description,
            prompt_template=strategy.prompt_template[:500],
            avg_score=strategy.avg_score or 0,
            success_rate=strategy.success_rate or 0,
            top_contexts=top_str,
            bottom_contexts=bottom_str,
        )

        try:
            result = await self.claude.chat(
                system_prompt="You are a teaching strategy designer. Respond with only JSON.",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
                temperature=0.7,
            )
            data = json.loads(result.strip())

            new_strategy = Strategy(
                name=data["name"],
                description=data["description"],
                strategy_type=strategy.strategy_type,
                prompt_template=data["prompt_template"],
                parent_strategy_id=strategy.id,
                generation=(strategy.generation or 0) + 1,
                is_active=True,
                is_baseline=False,
            )
            self.db.add(new_strategy)
            await self.db.flush()

            logger.info(
                "Mutated strategy",
                parent=strategy.name,
                child=new_strategy.name,
                generation=new_strategy.generation,
            )
            return new_strategy

        except (json.JSONDecodeError, KeyError):
            logger.warning("Failed to mutate strategy", name=strategy.name)
            return None

    async def _get_score_contexts(
        self, strategy_id, best: bool = True, limit: int = 3
    ) -> list[str]:
        """Get top or bottom scoring interaction contexts for a strategy."""
        order = StrategyScore.score.desc() if best else StrategyScore.score.asc()
        result = await self.db.execute(
            select(StrategyScore)
            .where(StrategyScore.strategy_id == strategy_id)
            .order_by(order)
            .limit(limit)
        )
        scores = result.scalars().all()
        contexts = []
        for s in scores:
            meta = s.context_metadata or {}
            desc = meta.get("concept", meta.get("topic", f"score={s.score:.2f}"))
            contexts.append(f"{desc} (score: {s.score:.2f})")
        return contexts
