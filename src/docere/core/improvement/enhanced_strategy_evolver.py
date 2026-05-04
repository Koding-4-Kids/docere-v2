"""Enhanced strategy evolution with robust validation and error handling."""

import json
import asyncio
from typing import Optional, List, Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from docere.config import settings
from docere.integrations.llm.client import ClaudeClient
from docere.models.conversation import Message
from docere.models.strategy import Strategy, StrategyScore
from docere.models.verification import InteractionScore
from .strategy_validation import StrategyValidator, RobustJSONExtractor

logger = structlog.get_logger()

MUTATION_PROMPT = """You are evolving a teaching strategy for an AI tutor.

Current strategy:
- Name: {name}
- Description: {description}
- Prompt template: {prompt_template}
- Average effectiveness score: {avg_score:.2f}
- Success rate: {success_rate:.1%}

Contexts where it performed BEST (with dimension breakdowns):
{top_contexts}

Contexts where it performed WORST (with dimension breakdowns):
{bottom_contexts}

CRITICAL REQUIREMENTS:
1. The new strategy must be pedagogically sound and student-centered
2. Include clear teaching instructions and interaction patterns
3. Address specific weaknesses shown in the worst-performing contexts
4. Maintain the core strengths from best-performing contexts

Generate an improved variant that:
- Improves on the identified weaknesses (clarity, engagement, helpfulness)
- Keeps the successful elements from top contexts
- Is different enough to test new approaches
- Follows sound educational principles

Respond with ONLY a valid JSON object:
{{"name": "Strategy Name (v2)", "description": "Brief description (50-200 chars)", "prompt_template": "Full teaching instructions (100-1500 chars)"}}"""


class CircuitBreaker:
    """Circuit breaker for external API calls."""
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    async def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        if self.state == "OPEN":
            if self._should_attempt_reset():
                self.state = "HALF_OPEN"
            else:
                raise Exception("Circuit breaker is OPEN")
        
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise e
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self.last_failure_time is None:
            return True
        import time
        return time.time() - self.last_failure_time > self.recovery_timeout
    
    def _on_success(self):
        """Reset circuit breaker on successful call."""
        self.failure_count = 0
        self.state = "CLOSED"
    
    def _on_failure(self):
        """Handle failure and potentially open circuit."""
        import time
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            logger.warning("Circuit breaker opened", failure_count=self.failure_count)


class EnhancedStrategyEvolver:
    """Enhanced strategy evolver with robust validation and error handling."""
    
    def __init__(self, db: AsyncSession, claude: ClaudeClient):
        self.db = db
        self.claude = claude
        self.validator = StrategyValidator()
        self.circuit_breaker = CircuitBreaker()
        self.json_extractor = RobustJSONExtractor()
    
    async def evolve(self) -> Dict[str, Any]:
        """Run one evolution cycle with enhanced error handling."""
        try:
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
            failed_mutations = []
            
            for strategy in scored[:top_k]:
                if (strategy.total_uses or 0) < 5:
                    continue  # Not enough data to evolve

                try:
                    new_strategy = await self._mutate_strategy_robust(strategy)
                    if new_strategy:
                        mutations.append(new_strategy.name)
                    else:
                        failed_mutations.append(strategy.name)
                except Exception as e:
                    logger.warning(
                        "Strategy mutation failed",
                        strategy_name=strategy.name,
                        error=str(e)
                    )
                    failed_mutations.append(strategy.name)

            # Step 2: Prune weak strategies
            pruned = await self._prune_weak_strategies(strategies)

            await self.db.flush()

            summary = {
                "mutations": len(mutations),
                "mutated_from": mutations,
                "failed_mutations": len(failed_mutations),
                "failed_strategy_names": failed_mutations,
                "pruned": len(pruned),
                "pruned_names": pruned,
                "active_count": len([s for s in strategies if s.is_active]),
                "circuit_breaker_state": self.circuit_breaker.state,
            }

            logger.info("Enhanced strategy evolution complete", **summary)
            return summary
            
        except Exception as e:
            logger.error("Strategy evolution failed", error=str(e))
            return {
                "mutations": 0,
                "pruned": 0,
                "error": str(e),
                "circuit_breaker_state": self.circuit_breaker.state,
            }
    
    async def _mutate_strategy_robust(self, strategy: Strategy) -> Optional[Strategy]:
        """Generate strategy variant with robust validation and retry logic."""
        max_attempts = 3
        
        for attempt in range(max_attempts):
            try:
                # Get contexts for mutation
                top_contexts = await self._get_score_contexts(strategy.id, best=True)
                bottom_contexts = await self._get_score_contexts(strategy.id, best=False)
                
                # Generate mutation with circuit breaker
                strategy_data = await self._generate_mutation_with_retry(
                    strategy, top_contexts, bottom_contexts
                )
                
                if not strategy_data:
                    continue
                
                # Validate generated strategy
                is_valid, errors = await self.validator.validate_strategy(strategy_data)
                if not is_valid:
                    logger.warning(
                        "Generated strategy failed validation",
                        strategy_name=strategy.name,
                        attempt=attempt + 1,
                        errors=errors
                    )
                    continue
                
                # Check similarity to existing strategies
                if await self._is_too_similar_enhanced(strategy_data["prompt_template"]):
                    logger.info(
                        "Rejected mutation — too similar to existing strategy",
                        parent=strategy.name,
                        proposed_name=strategy_data.get("name", "?"),
                        attempt=attempt + 1
                    )
                    continue
                
                # Create and return new strategy
                return await self._create_validated_strategy(strategy, strategy_data)
                
            except Exception as e:
                logger.warning(
                    "Mutation attempt failed",
                    strategy_name=strategy.name,
                    attempt=attempt + 1,
                    error=str(e)
                )
                if attempt == max_attempts - 1:
                    raise
                
                # Exponential backoff
                await asyncio.sleep(2 ** attempt)
        
        return None
    
    async def _generate_mutation_with_retry(
        self, 
        strategy: Strategy, 
        top_contexts: List[str], 
        bottom_contexts: List[str]
    ) -> Optional[Dict[str, Any]]:
        """Generate mutation with circuit breaker and retry logic."""
        
        # Prepare context strings with smart truncation
        top_str = self._format_contexts(top_contexts, "No strong examples yet")
        bottom_str = self._format_contexts(bottom_contexts, "No weak examples yet")
        
        # Smart prompt template truncation
        template_preview = self._smart_truncate_template(strategy.prompt_template, 400)
        
        prompt = MUTATION_PROMPT.format(
            name=strategy.name,
            description=strategy.description,
            prompt_template=template_preview,
            avg_score=strategy.avg_score or 0,
            success_rate=strategy.success_rate or 0,
            top_contexts=top_str,
            bottom_contexts=bottom_str,
        )
        
        async def claude_call():
            return await self.claude.chat(
                system_prompt="You are a teaching strategy designer. Respond with only valid JSON.",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=800,
                temperature=0.5,  # Lower temperature for more consistent output
            )
        
        try:
            # Use circuit breaker for Claude API call
            result = await self.circuit_breaker.call(claude_call)
            
            # Robust JSON extraction
            strategy_data = self.json_extractor.extract_json(result)
            
            if not strategy_data:
                logger.warning(
                    "Failed to extract JSON from Claude response",
                    strategy_name=strategy.name,
                    response_preview=result[:200]
                )
                return None
            
            return strategy_data
            
        except Exception as e:
            logger.error(
                "Claude API call failed",
                strategy_name=strategy.name,
                error=str(e)
            )
            raise
    
    def _format_contexts(self, contexts: List[str], fallback: str) -> str:
        """Format context strings with proper fallback."""
        if not contexts:
            return fallback
        
        formatted = []
        for i, context in enumerate(contexts[:3], 1):  # Limit to top 3
            formatted.append(f"{i}. {context}")
        
        return "\n".join(formatted)
    
    def _smart_truncate_template(self, template: str, max_length: int) -> str:
        """Truncate template at sentence boundaries when possible."""
        if len(template) <= max_length:
            return template
        
        # Try to cut at sentence boundary
        sentences = template.split('. ')
        result = ""
        
        for sentence in sentences:
            if len(result + sentence + '. ') > max_length:
                break
            result += sentence + '. '
        
        if result:
            return result.rstrip('. ') + "..."
        
        # Fallback to character truncation
        return template[:max_length - 3] + "..."
    
    async def _is_too_similar_enhanced(self, new_template: str, threshold: float = 0.75) -> bool:
        """Enhanced similarity check with better preprocessing."""
        result = await self.db.execute(
            select(Strategy.prompt_template).where(Strategy.is_active.is_(True))
        )
        
        # Preprocess new template
        new_words = self._preprocess_template(new_template)
        if not new_words:
            return False
        
        for (existing_template,) in result.all():
            existing_words = self._preprocess_template(existing_template)
            if not existing_words:
                continue
            
            # Jaccard similarity
            intersection = len(new_words & existing_words)
            union = len(new_words | existing_words)
            similarity = intersection / union if union > 0 else 0
            
            if similarity > threshold:
                return True
        
        return False
    
    def _preprocess_template(self, template: str) -> set:
        """Preprocess template for similarity comparison."""
        # Convert to lowercase and split
        words = template.lower().split()
        
        # Remove common stop words and punctuation
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
        
        processed_words = set()
        for word in words:
            # Remove punctuation
            clean_word = ''.join(char for char in word if char.isalnum())
            if len(clean_word) > 2 and clean_word not in stop_words:
                processed_words.add(clean_word)
        
        return processed_words
    
    async def _create_validated_strategy(
        self, 
        parent_strategy: Strategy, 
        strategy_data: Dict[str, Any]
    ) -> Strategy:
        """Create a new validated strategy."""
        new_strategy = Strategy(
            name=strategy_data["name"],
            description=strategy_data["description"],
            strategy_type=parent_strategy.strategy_type,
            prompt_template=strategy_data["prompt_template"],
            parent_strategy_id=parent_strategy.id,
            generation=(parent_strategy.generation or 0) + 1,
            is_active=True,
            is_baseline=False,
        )
        
        self.db.add(new_strategy)
        await self.db.flush()
        
        logger.info(
            "Created validated strategy",
            parent=parent_strategy.name,
            child=new_strategy.name,
            generation=new_strategy.generation,
        )
        
        return new_strategy
    
    async def _prune_weak_strategies(self, strategies: List[Strategy]) -> List[str]:
        """Prune weak strategies with enhanced criteria."""
        pruned = []
        min_uses = getattr(settings, 'strategy_min_uses_for_prune', 20)
        threshold = getattr(settings, 'strategy_prune_score_threshold', 0.3)
        
        for strategy in strategies:
            if strategy.is_baseline:
                continue  # Never prune seed strategies
            
            should_prune = (
                (strategy.total_uses or 0) >= min_uses and 
                (strategy.avg_score or 0) < threshold
            )
            
            if should_prune:
                strategy.is_active = False
                pruned.append(strategy.name)
                logger.info(
                    "Pruned weak strategy",
                    name=strategy.name,
                    uses=strategy.total_uses,
                    avg_score=strategy.avg_score,
                )
        
        return pruned
    
    async def _get_score_contexts(
        self, strategy_id: int, best: bool = True, limit: int = 3
    ) -> List[str]:
        """Get top or bottom scoring interaction contexts for a strategy."""
        order = StrategyScore.score.desc() if best else StrategyScore.score.asc()

        result = await self.db.execute(
            select(
                StrategyScore.score,
                StrategyScore.context_metadata,
                Message.content,
                Message.role,
            )
            .outerjoin(InteractionScore, StrategyScore.interaction_score_id == InteractionScore.id)
            .outerjoin(Message, InteractionScore.message_id == Message.id)
            .where(StrategyScore.strategy_id == strategy_id)
            .order_by(order)
            .limit(limit)
        )
        rows = result.all()

        contexts = []
        for score_val, meta, msg_content, msg_role in rows:
            meta = meta or {}
            topic = meta.get("concept", meta.get("topic", ""))

            parts = []
            if topic:
                parts.append(f"Topic: {topic}")

            # Include individual dimension scores
            for dim in ("helpfulness", "clarity", "engagement"):
                val = meta.get(dim)
                if val is not None:
                    parts.append(f"{dim.title()}: {val:.2f}")

            delta = meta.get("understanding_delta")
            if delta is not None:
                parts.append(f"Understanding Δ: {delta:+.2f}")

            followup = meta.get("followup_type")
            if followup:
                parts.append(f"Followup: {followup}")

            if msg_content:
                # Truncate message content appropriately
                content_preview = msg_content[:100] + "..." if len(msg_content) > 100 else msg_content
                parts.append(f"Response: {content_preview}")

            parts.append(f"Score: {score_val:.2f}")
            contexts.append(" | ".join(parts))

        return contexts
