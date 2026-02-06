"""Pydantic schemas for chat endpoints."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class CreateConversationRequest(BaseModel):
    course_id: uuid.UUID
    assignment_id: uuid.UUID | None = None
    title: str | None = None


class SendMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=10000)


class MessageResponse(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    model_used: str | None = None
    token_count: int | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationResponse(BaseModel):
    id: uuid.UUID
    course_id: uuid.UUID
    assignment_id: uuid.UUID | None = None
    title: str | None = None
    status: str
    strategy_used: str | None = None
    started_at: datetime
    last_message_at: datetime

    model_config = {"from_attributes": True}


class ConversationDetailResponse(ConversationResponse):
    messages: list[MessageResponse] = []


class AgentMessageResponse(BaseModel):
    message: MessageResponse
    strategy_used: str | None = None
    memory_context_tokens: int = 0
