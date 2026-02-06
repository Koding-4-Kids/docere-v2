"""Chat/tutoring conversation endpoints."""

from fastapi import APIRouter

router = APIRouter()


@router.post("/conversations")
async def create_conversation() -> dict[str, str]:
    """Start a new tutoring conversation."""
    # TODO: Create conversation, optionally link to assignment
    return {"status": "not_implemented"}


@router.get("/conversations")
async def list_conversations() -> dict[str, str]:
    """List student's conversations."""
    # TODO: Return paginated conversation list
    return {"status": "not_implemented"}


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str) -> dict[str, str]:
    """Get conversation with message history."""
    # TODO: Return conversation with messages
    return {"status": "not_implemented"}


@router.post("/conversations/{conversation_id}/messages")
async def send_message(conversation_id: str) -> dict[str, str]:
    """Send a message and get AI response.

    This is the main tutoring endpoint. Flow:
    1. Retrieve memory context (teacher + student + interaction history)
    2. Select teaching strategy (UCB1 bandit)
    3. Build system prompt with memory + strategy
    4. Call Claude API
    5. Async: capture memory, queue process verification
    """
    # TODO: Implement full agent pipeline
    return {"status": "not_implemented"}
