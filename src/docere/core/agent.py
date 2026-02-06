"""Main tutoring agent orchestrator.

For each student message:
1. Retrieves memory context (teacher + student + interaction history)
2. Selects an intervention strategy (UCB1 bandit or default)
3. Builds a system prompt incorporating all context
4. Calls Claude API
5. Triggers async post-processing (memory capture, scoring)
"""

from dataclasses import dataclass


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
        # TODO: Step 1 - Retrieve memory context (gated by study_group)
        # TODO: Step 2 - Select teaching strategy (gated by study_group)
        # TODO: Step 3 - Build system prompt with memory + strategy
        # TODO: Step 4 - Call Claude API
        # TODO: Step 5 - Async post-processing (memory capture, queue scoring)
        raise NotImplementedError
