"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-02-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── users ──
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("external_lms_id", sa.String(255)),
        sa.Column("lms_platform", sa.String(50)),
        sa.Column("email", sa.String(255), unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("role", sa.String(50), nullable=False, server_default="student"),
        sa.Column("avatar_url", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("external_lms_id", "lms_platform", name="uq_user_lms"),
    )

    # ── courses ──
    op.create_table(
        "courses",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("external_lms_id", sa.String(255)),
        sa.Column("lms_platform", sa.String(50)),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("course_code", sa.String(100)),
        sa.Column("instructor_id", UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("syllabus_text", sa.Text),
        sa.Column("syllabus_embedding_id", sa.String(255)),
        sa.Column("term", sa.String(100)),
        sa.Column("lms_sync_enabled", sa.Boolean, server_default="true"),
        sa.Column("last_synced_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("external_lms_id", "lms_platform", name="uq_course_lms"),
    )

    # ── enrollments ──
    op.create_table(
        "enrollments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("course_id", UUID(as_uuid=True), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lms_role", sa.String(50), server_default="student"),
        sa.Column("study_group", sa.String(50)),
        sa.Column("enrolled_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "course_id", name="uq_enrollment"),
    )

    # ── assignments ──
    op.create_table(
        "assignments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("course_id", UUID(as_uuid=True), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("external_lms_id", sa.String(255)),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("due_at", sa.DateTime(timezone=True)),
        sa.Column("points_possible", sa.Float),
        sa.Column("assignment_type", sa.String(100)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── submissions ──
    op.create_table(
        "submissions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("assignment_id", UUID(as_uuid=True), sa.ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("external_lms_id", sa.String(255)),
        sa.Column("score", sa.Float),
        sa.Column("grade", sa.String(20)),
        sa.Column("submitted_at", sa.DateTime(timezone=True)),
        sa.Column("graded_at", sa.DateTime(timezone=True)),
        sa.Column("workflow_state", sa.String(50), server_default="submitted"),
        sa.Column("synced_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── course_materials ──
    op.create_table(
        "course_materials",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("course_id", UUID(as_uuid=True), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("material_type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(500)),
        sa.Column("content", sa.Text),
        sa.Column("source_url", sa.Text),
        sa.Column("embedding_id", sa.String(255)),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── strategies ──
    op.create_table(
        "strategies",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("strategy_type", sa.String(100), nullable=False),
        sa.Column("prompt_template", sa.Text, nullable=False),
        sa.Column("applicable_contexts", JSONB, server_default="{}"),
        sa.Column("total_uses", sa.Integer, server_default="0"),
        sa.Column("avg_score", sa.Float),
        sa.Column("success_rate", sa.Float),
        sa.Column("confidence_interval", sa.Float),
        sa.Column("parent_strategy_id", UUID(as_uuid=True), sa.ForeignKey("strategies.id")),
        sa.Column("generation", sa.Integer, server_default="0"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("is_baseline", sa.Boolean, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
    )

    # ── conversations ──
    op.create_table(
        "conversations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("student_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("course_id", UUID(as_uuid=True), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("assignment_id", UUID(as_uuid=True), sa.ForeignKey("assignments.id")),
        sa.Column("title", sa.String(500)),
        sa.Column("status", sa.String(50), server_default="active"),
        sa.Column("strategy_id", UUID(as_uuid=True), sa.ForeignKey("strategies.id")),
        sa.Column("study_group", sa.String(50)),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_message_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── messages ──
    op.create_table(
        "messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("conversation_id", UUID(as_uuid=True), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("embedding_id", sa.String(255)),
        sa.Column("token_count", sa.Integer),
        sa.Column("model_used", sa.String(100)),
        sa.Column("metadata", JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_messages_conversation", "messages", ["conversation_id", "created_at"])
    op.create_index("idx_messages_role", "messages", ["conversation_id", "role"])

    # ── memory_records ──
    op.create_table(
        "memory_records",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("student_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("course_id", UUID(as_uuid=True), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("memory_type", sa.String(50), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("embedding_id", sa.String(255)),
        sa.Column("concepts", ARRAY(sa.String)),
        sa.Column("sentiment", sa.String(50)),
        sa.Column("confusion_score", sa.Float, server_default="0.0"),
        sa.Column("source", sa.String(100)),
        sa.Column("source_message_id", UUID(as_uuid=True), sa.ForeignKey("messages.id")),
        sa.Column("metadata", JSONB, server_default="{}"),
        sa.Column("is_compressed", sa.Boolean, server_default="false"),
        sa.Column("compressed_into", UUID(as_uuid=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
    )
    op.create_index("idx_memory_student_course", "memory_records", ["student_id", "course_id", "memory_type"])
    op.create_index("idx_memory_created", "memory_records", ["created_at"])

    # ── student_profiles ──
    op.create_table(
        "student_profiles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("student_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("course_id", UUID(as_uuid=True), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("total_interactions", sa.Integer, server_default="0"),
        sa.Column("total_messages", sa.Integer, server_default="0"),
        sa.Column("avg_confusion_score", sa.Float, server_default="0.0"),
        sa.Column("avg_interaction_score", sa.Float, server_default="0.0"),
        sa.Column("engagement_level", sa.String(50), server_default="unknown"),
        sa.Column("current_grade", sa.Float),
        sa.Column("last_interaction_at", sa.DateTime(timezone=True)),
        sa.Column("avg_session_duration_minutes", sa.Float),
        sa.Column("preferred_interaction_times", JSONB),
        sa.Column("profile_summary", sa.Text),
        sa.Column("profile_embedding_id", sa.String(255)),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("student_id", "course_id", name="uq_student_profile"),
    )

    # ── concept_mastery ──
    op.create_table(
        "concept_mastery",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("student_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("course_id", UUID(as_uuid=True), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("concept_name", sa.String(255), nullable=False),
        sa.Column("mastery_level", sa.Float, server_default="0.0"),
        sa.Column("times_practiced", sa.Integer, server_default="0"),
        sa.Column("times_struggled", sa.Integer, server_default="0"),
        sa.Column("last_practiced_at", sa.DateTime(timezone=True)),
        sa.Column("evidence", JSONB, server_default="[]"),
        sa.UniqueConstraint("student_id", "course_id", "concept_name", name="uq_concept_mastery"),
    )

    # ── interaction_scores ──
    op.create_table(
        "interaction_scores",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("message_id", UUID(as_uuid=True), sa.ForeignKey("messages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("conversation_id", UUID(as_uuid=True), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("helpfulness_score", sa.Float),
        sa.Column("clarity_score", sa.Float),
        sa.Column("engagement_score", sa.Float),
        sa.Column("understanding_delta", sa.Float),
        sa.Column("student_followup_type", sa.String(50)),
        sa.Column("time_to_next_message_seconds", sa.Integer),
        sa.Column("subsequent_performance", sa.Float),
        sa.Column("composite_score", sa.Float),
        sa.Column("scoring_method", sa.String(50)),
        sa.Column("scoring_metadata", JSONB, server_default="{}"),
        sa.Column("scored_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_interaction_scores_student", "interaction_scores", ["student_id", "scored_at"])
    op.create_index("idx_interaction_scores_conversation", "interaction_scores", ["conversation_id"])

    # ── strategy_scores ──
    op.create_table(
        "strategy_scores",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("strategy_id", UUID(as_uuid=True), sa.ForeignKey("strategies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("conversation_id", UUID(as_uuid=True), sa.ForeignKey("conversations.id")),
        sa.Column("interaction_score_id", UUID(as_uuid=True), sa.ForeignKey("interaction_scores.id")),
        sa.Column("score", sa.Float, nullable=False),
        sa.Column("context_metadata", JSONB, server_default="{}"),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_strategy_scores_strategy", "strategy_scores", ["strategy_id", "recorded_at"])

    # ── study_config ──
    op.create_table(
        "study_config",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("course_id", UUID(as_uuid=True), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("study_name", sa.String(500)),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("groups", JSONB, nullable=False),
        sa.Column("randomization_seed", sa.Integer),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── research_events ──
    op.create_table(
        "research_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("study_id", UUID(as_uuid=True), sa.ForeignKey("study_config.id"), nullable=False),
        sa.Column("student_id", UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("event_data", JSONB, nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_research_events", "research_events", ["study_id", "student_id", "event_type", "recorded_at"])

    # ── alerts ──
    op.create_table(
        "alerts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("instructor_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("course_id", UUID(as_uuid=True), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("alert_type", sa.String(100), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("title", sa.String(500)),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("recommended_action", sa.Text),
        sa.Column("evidence", JSONB, server_default="{}"),
        sa.Column("is_read", sa.Boolean, server_default="false"),
        sa.Column("is_resolved", sa.Boolean, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
    )
    op.create_index("idx_alerts_instructor", "alerts", ["instructor_id", "is_read", "created_at"])

    # ── learning_analytics_events ──
    op.create_table(
        "learning_analytics_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("student_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("course_id", UUID(as_uuid=True), sa.ForeignKey("courses.id")),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("event_data", JSONB, nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_analytics_student_course", "learning_analytics_events", ["student_id", "course_id", "event_type"])
    op.create_index("idx_analytics_time", "learning_analytics_events", ["recorded_at"])


def downgrade() -> None:
    op.drop_table("learning_analytics_events")
    op.drop_table("alerts")
    op.drop_table("research_events")
    op.drop_table("study_config")
    op.drop_table("strategy_scores")
    op.drop_table("interaction_scores")
    op.drop_table("concept_mastery")
    op.drop_table("student_profiles")
    op.drop_table("memory_records")
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_table("strategies")
    op.drop_table("course_materials")
    op.drop_table("submissions")
    op.drop_table("assignments")
    op.drop_table("enrollments")
    op.drop_table("courses")
    op.drop_table("users")
