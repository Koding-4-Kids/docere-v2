"""Chat/tutoring conversation endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from docere.core.graphs.tutoring import run_tutoring_graph
from docere.dependencies import get_claude, get_current_user_id, get_db, get_qdrant
from docere.integrations.llm.client import ClaudeClient
from docere.integrations.vector_db.qdrant import QdrantStore
from docere.models.conversation import Conversation, Message
from docere.models.course import Enrollment
from docere.schemas.chat import (
    AgentMessageResponse,
    ConversationDetailResponse,
    ConversationResponse,
    CreateConversationRequest,
    MeetingAction,
    MessageResponse,
    SendMessageRequest,
    StudyArtifact,
)

router = APIRouter()


@router.post("/conversations", response_model=ConversationResponse)
async def create_conversation(
    request: CreateConversationRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> Conversation:
    """Start a new tutoring conversation."""
    # Look up student's study group for feature gating
    enrollment = await db.execute(
        select(Enrollment).where(
            Enrollment.user_id == user_id,
            Enrollment.course_id == request.course_id,
        )
    )
    enrollment_row = enrollment.scalar_one_or_none()
    study_group = enrollment_row.study_group if enrollment_row else None

    conversation = Conversation(
        student_id=user_id,
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
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[Conversation]:
    """List student's conversations."""
    query = select(Conversation).where(
        Conversation.student_id == user_id,
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
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> Conversation:
    """Get conversation with message history."""
    result = await db.execute(
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .where(
            Conversation.id == conversation_id,
            Conversation.student_id == user_id,
        )
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@router.delete("/conversations/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Soft-delete a conversation."""
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.student_id == user_id,
        )
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    conversation.status = "deleted"
    await db.commit()


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=AgentMessageResponse,
)
async def send_message(
    conversation_id: uuid.UUID,
    request: SendMessageRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    qdrant: QdrantStore = Depends(get_qdrant),
    claude: ClaudeClient = Depends(get_claude),
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
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.student_id == user_id,
        )
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Run the LangGraph tutoring pipeline
    agent_response = await run_tutoring_graph(
        db=db,
        qdrant=qdrant,
        claude=claude,
        conversation_id=str(conversation_id),
        student_message=request.content,
        student_id=str(user_id),
        course_id=str(conversation.course_id),
        assignment_id=str(conversation.assignment_id) if conversation.assignment_id else None,
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

    # Extract artifact and action from message metadata if present
    artifact = None
    action = None
    metadata = assistant_msg.metadata_ or {}

    artifact_data = metadata.get("artifact")
    if artifact_data and isinstance(artifact_data, dict):
        try:
            artifact = StudyArtifact(**artifact_data)
        except Exception:
            artifact = None

    action_data = metadata.get("action")
    if action_data and isinstance(action_data, dict):
        try:
            action = MeetingAction(**action_data)
        except Exception:
            action = None

    widgets_data = metadata.get("widgets")
    widgets = widgets_data if isinstance(widgets_data, list) else None

    return AgentMessageResponse(
        message=MessageResponse(
            id=assistant_msg.id,
            role=assistant_msg.role,
            content=assistant_msg.content,
            model_used=assistant_msg.model_used,
            token_count=assistant_msg.token_count,
            created_at=assistant_msg.created_at,
            artifact=artifact,
            action=action,
            widgets=widgets,
        ),
        strategy_used=agent_response.strategy_used,
        memory_context_tokens=agent_response.memory_context_size,
    )
