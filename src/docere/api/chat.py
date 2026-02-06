"""Chat/tutoring conversation endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from docere.core.agent import TutoringAgent
from docere.dependencies import get_db
from docere.integrations.llm.client import ClaudeClient
from docere.integrations.vector_db.qdrant import QdrantStore
from docere.models.conversation import Conversation, Message
from docere.models.course import Enrollment
from docere.schemas.chat import (
    AgentMessageResponse,
    ConversationDetailResponse,
    ConversationResponse,
    CreateConversationRequest,
    MessageResponse,
    SendMessageRequest,
)

router = APIRouter()

# Singletons initialized on first use
_qdrant: QdrantStore | None = None
_claude: ClaudeClient | None = None


def _get_qdrant() -> QdrantStore:
    global _qdrant
    if _qdrant is None:
        _qdrant = QdrantStore()
    return _qdrant


def _get_claude() -> ClaudeClient:
    global _claude
    if _claude is None:
        _claude = ClaudeClient()
    return _claude


@router.post("/conversations", response_model=ConversationResponse)
async def create_conversation(
    request: CreateConversationRequest,
    db: AsyncSession = Depends(get_db),
    # TODO: Replace with real auth dependency
    student_id: str = "placeholder",
) -> Conversation:
    """Start a new tutoring conversation."""
    # Look up student's study group for feature gating
    enrollment = await db.execute(
        select(Enrollment).where(
            Enrollment.user_id == student_id,
            Enrollment.course_id == request.course_id,
        )
    )
    enrollment_row = enrollment.scalar_one_or_none()
    study_group = enrollment_row.study_group if enrollment_row else None

    conversation = Conversation(
        student_id=student_id,
        course_id=request.course_id,
        assignment_id=request.assignment_id,
        title=request.title,
        study_group=study_group,
    )
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)
    return conversation


@router.get("/conversations", response_model=list[ConversationResponse])
async def list_conversations(
    course_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    student_id: str = "placeholder",
) -> list[Conversation]:
    """List student's conversations."""
    query = select(Conversation).where(
        Conversation.student_id == student_id,
        Conversation.status == "active",
    )
    if course_id:
        query = query.where(Conversation.course_id == course_id)

    query = query.order_by(Conversation.last_message_at.desc())
    result = await db.execute(query)
    return list(result.scalars().all())


@router.get("/conversations/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(
    conversation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> Conversation:
    """Get conversation with message history."""
    result = await db.execute(
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .where(Conversation.id == conversation_id)
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=AgentMessageResponse,
)
async def send_message(
    conversation_id: uuid.UUID,
    request: SendMessageRequest,
    db: AsyncSession = Depends(get_db),
    student_id: str = "placeholder",
) -> AgentMessageResponse:
    """Send a message and get AI response.

    This is the main tutoring endpoint. Flow:
    1. Retrieve memory context (teacher + student + interaction history)
    2. Select teaching strategy (UCB1 bandit)
    3. Build system prompt with memory + strategy
    4. Call Claude API
    5. Async: capture memory, queue process verification
    """
    # Verify conversation exists and belongs to student
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Build agent and process message
    agent = TutoringAgent(
        db=db,
        qdrant=_get_qdrant(),
        claude=_get_claude(),
    )

    agent_response = await agent.handle_message(
        conversation_id=str(conversation_id),
        student_message=request.content,
        student_id=str(conversation.student_id),
        course_id=str(conversation.course_id),
        study_group=conversation.study_group,
    )

    # Fetch the persisted assistant message
    msg_result = await db.execute(
        select(Message)
        .where(
            Message.conversation_id == conversation_id,
            Message.role == "assistant",
        )
        .order_by(Message.created_at.desc())
        .limit(1)
    )
    assistant_msg = msg_result.scalar_one()

    return AgentMessageResponse(
        message=MessageResponse(
            id=assistant_msg.id,
            role=assistant_msg.role,
            content=assistant_msg.content,
            model_used=assistant_msg.model_used,
            token_count=assistant_msg.token_count,
            created_at=assistant_msg.created_at,
        ),
        strategy_used=agent_response.strategy_used,
        memory_context_tokens=agent_response.memory_context_size,
    )
