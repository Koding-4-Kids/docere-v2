"""Main tutoring agent orchestrator.

For each student message:
1. Retrieves memory context (teacher + student + interaction history)
2. Selects an intervention strategy (UCB1 bandit or default)
3. Builds a system prompt incorporating all context
4. Calls Claude API
5. Triggers async post-processing (memory capture, scoring)
"""

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from docere.core.improvement.strategy_archive import StrategyArchive
from docere.core.memory.memory_layer import MemoryContext, MemoryLayer
from docere.integrations.llm.client import ClaudeClient
from docere.integrations.vector_db.qdrant import QdrantStore
from docere.models.conversation import Conversation, Message

logger = structlog.get_logger()

BASE_SYSTEM_PROMPT = """You are Docere, an AI tutoring assistant integrated into the student's course.
Your role is to help students learn effectively - not to give them answers.

Guidelines:
- Be encouraging and patient
- Ask clarifying questions when the student's question is vague
- Use the student's learning history to personalize your responses
- Reference course materials when relevant
- If the student seems frustrated, acknowledge it and try a different approach
- Keep responses concise and focused"""


@dataclass
class AgentResponse:
    """Response from the tutoring agent."""

    content: str
    model_used: str
    token_count: int
    strategy_used: str | None
    memory_context_size: int


class TutoringAgent:
    """Central agent that coordinates memory, strategy, and LLM calls."""

    def __init__(
        self,
        db: AsyncSession,
        qdrant: QdrantStore,
        claude: ClaudeClient,
    ):
        self.db = db
        self.claude = claude
        self.memory = MemoryLayer(db, qdrant, claude)
        self.strategies = StrategyArchive(db)

    async def handle_message(
        self,
        conversation_id: str,
        student_message: str,
        student_id: str,
        course_id: str,
        study_group: str | None = None,
    ) -> AgentResponse:
        """Process a student message and generate a tutoring response.

        Args:
            conversation_id: Active conversation ID
            student_message: The student's message
            student_id: Student user ID
            course_id: Course context ID
            study_group: Research study group (controls feature gating)

        Returns:
            AgentResponse with the AI tutoring response
        """
        # Step 1: Retrieve memory context (gated by study_group)
        if study_group == "control":
            memory_ctx = MemoryContext.empty()
        else:
            memory_ctx = await self.memory.retrieve_context(
                student_id=student_id,
                course_id=course_id,
                current_query=student_message,
            )

        # Step 2: Select teaching strategy (gated by study_group)
        strategy = await self.strategies.select_strategy(study_group)
        strategy_name = strategy.name if strategy else None

        # Step 3: Build system prompt
        system_prompt = self._build_system_prompt(memory_ctx, strategy)

        # Step 4: Build message history + new message, call Claude
        conversation_messages = await self._get_conversation_history(conversation_id)
        conversation_messages.append({"role": "user", "content": student_message})

        response_text = await self.claude.chat(
            system_prompt=system_prompt,
            messages=conversation_messages,
            max_tokens=1024,
            temperature=0.7,
        )

        # Step 5: Persist messages
        now = datetime.now(timezone.utc)

        student_msg = Message(
            conversation_id=conversation_id,
            role="user",
            content=student_message,
            created_at=now,
        )
        self.db.add(student_msg)

        assistant_msg = Message(
            conversation_id=conversation_id,
            role="assistant",
            content=response_text,
            model_used=self.claude.default_model,
            token_count=len(response_text) // 4,
            metadata_={
                "strategy_id": str(strategy.id) if strategy else None,
                "strategy_name": strategy_name,
                "memory_tokens": memory_ctx.total_tokens,
            },
            created_at=now,
        )
        self.db.add(assistant_msg)

        # Update conversation timestamp
        result = await self.db.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        conversation = result.scalar_one_or_none()
        if conversation:
            conversation.last_message_at = now
            if strategy:
                conversation.strategy_id = strategy.id

        await self.db.flush()

        # Step 6: Async post-processing (memory capture)
        # Run in background - don't block the response
        await self.memory.capture_interaction(
            student_id=student_id,
            course_id=course_id,
            student_message=student_message,
            agent_response=response_text,
        )

        await self.db.commit()

        logger.info(
            "Agent response generated",
            conversation_id=conversation_id,
            strategy=strategy_name,
            memory_tokens=memory_ctx.total_tokens,
        )

        return AgentResponse(
            content=response_text,
            model_used=self.claude.default_model,
            token_count=len(response_text) // 4,
            strategy_used=strategy_name,
            memory_context_size=memory_ctx.total_tokens,
        )

    def _build_system_prompt(
        self, memory_ctx: MemoryContext, strategy: object | None
    ) -> str:
        """Build the full system prompt from memory context and strategy."""
        parts = [BASE_SYSTEM_PROMPT]

        # Add strategy instructions
        if strategy and hasattr(strategy, "prompt_template") and strategy.prompt_template:
            parts.append(f"\n## Teaching Strategy\n{strategy.prompt_template}")

        # Add memory context
        context_str = memory_ctx.to_system_context()
        if context_str:
            parts.append(f"\n## Student Context\n{context_str}")

        return "\n".join(parts)

    async def _get_conversation_history(
        self, conversation_id: str, max_messages: int = 20
    ) -> list[dict[str, str]]:
        """Fetch recent conversation history for Claude context."""
        result = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(max_messages)
        )
        messages = list(reversed(result.scalars().all()))

        return [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]
