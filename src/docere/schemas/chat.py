"""Pydantic schemas for chat endpoints."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class StudyArtifact(BaseModel):
    """A study material artifact generated alongside a chat message."""

    type: Literal["notes", "flashcards", "study_guide", "slides"]
    title: str = ""
    content: str
    source_concepts: list[str] = []

    @field_validator("content", mode="before")
    @classmethod
    def coerce_content_to_str(cls, v: object) -> str:
        """Content may have been stored as a parsed list/dict — re-serialize."""
        if not isinstance(v, str):
            import json

            return json.dumps(v)
        return v


class MeetingAction(BaseModel):
    """An action block from the agent suggesting a meeting."""

    type: Literal["meeting_suggestion"]
    reason: str
    concepts: list[str] = []


# ── Student Widget Schemas ──


class QuizQuestion(BaseModel):
    question: str
    choices: list[str] = []
    correct_index: int | None = None
    correct_answer: str = ""
    explanation: str = ""


class PracticeQuizWidget(BaseModel):
    type: Literal["practice_quiz"]
    title: str
    concept: str = ""
    questions: list[QuizQuestion]


class StepHint(BaseModel):
    text: str


class StepHintsWidget(BaseModel):
    type: Literal["step_hints"]
    title: str
    problem_context: str = ""
    hints: list[StepHint]


# ── Instructor Widget Schemas ──


class StudentCardWidget(BaseModel):
    type: Literal["student_card"]
    student_name: str
    student_id: str
    engagement_level: str
    confusion_label: str
    grade_label: str
    total_interactions: int
    top_concepts: list[dict] = []
    recent_activity: str = ""
    profile_summary: str = ""


class AtRiskRow(BaseModel):
    student_name: str
    student_id: str
    risk_reason: str
    confusion_label: str
    engagement_level: str
    grade_label: str
    recommended_action: str


class AtRiskTableWidget(BaseModel):
    type: Literal["at_risk_table"]
    title: str
    students: list[AtRiskRow]


class HeatmapCell(BaseModel):
    concept: str
    mastery_label: str
    mastery_value: float
    student_count: int
    times_struggled: int


class ConceptHeatmapWidget(BaseModel):
    type: Literal["concept_heatmap"]
    title: str
    cells: list[HeatmapCell]


class EngagementBucket(BaseModel):
    level: str
    count: int
    student_names: list[str] = []


class EngagementChartWidget(BaseModel):
    type: Literal["engagement_chart"]
    title: str
    total_students: int
    buckets: list[EngagementBucket]


# ── Request / Response Schemas ──


class CreateConversationRequest(BaseModel):
    course_id: uuid.UUID
    assignment_id: uuid.UUID | None = None
    title: str | None = None


class SendMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=10000)
    notes_content: str | None = Field(None, max_length=20000)


class MessageResponse(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    model_used: str | None = None
    token_count: int | None = None
    created_at: datetime
    artifact: StudyArtifact | None = None
    action: MeetingAction | None = None
    widgets: list[dict] | None = None

    model_config = {"from_attributes": True}


class InstructorQueryResponse(BaseModel):
    answer: str
    widgets: list[dict] = []


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
