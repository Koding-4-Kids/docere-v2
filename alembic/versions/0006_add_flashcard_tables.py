"""Add flashcard spaced repetition tables.

Revision ID: 0006
Revises: 0005
"""

from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # FlashcardDeck — one per student per course
    op.create_table(
        "flashcard_decks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "student_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "course_id",
            UUID(as_uuid=True),
            sa.ForeignKey("courses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(500), nullable=False, server_default="Flashcards"),
        sa.Column("card_count", sa.Integer, server_default="0", nullable=False),
        sa.Column("last_reviewed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("student_id", "course_id", name="uq_deck_student_course"),
    )

    # FlashcardCard — individual cards with FSRS state
    op.create_table(
        "flashcard_cards",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "deck_id",
            UUID(as_uuid=True),
            sa.ForeignKey("flashcard_decks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "student_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("front", sa.Text, nullable=False),
        sa.Column("back", sa.Text, nullable=False),
        sa.Column("front_hash", sa.String(64), nullable=False),
        sa.Column(
            "source_message_id",
            UUID(as_uuid=True),
            sa.ForeignKey("messages.id"),
        ),
        sa.Column("concepts", sa.ARRAY(sa.String)),
        sa.Column("fsrs_state", JSONB, server_default="{}"),
        sa.Column(
            "due_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("stability", sa.Float, server_default="0.0"),
        sa.Column("difficulty", sa.Float, server_default="0.0"),
        sa.Column("reps", sa.Integer, server_default="0"),
        sa.Column("lapses", sa.Integer, server_default="0"),
        sa.Column("state", sa.String(20), server_default="new"),
        sa.Column("is_suspended", sa.Boolean, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("deck_id", "front_hash", name="uq_card_front_per_deck"),
    )
    op.create_index("idx_card_deck", "flashcard_cards", ["deck_id"])
    op.create_index("idx_card_due", "flashcard_cards", ["student_id", "due_at"])

    # CardReview — audit trail
    op.create_table(
        "card_reviews",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "card_id",
            UUID(as_uuid=True),
            sa.ForeignKey("flashcard_cards.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "student_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("rating", sa.Integer, nullable=False),
        sa.Column("review_duration_ms", sa.Integer),
        sa.Column(
            "reviewed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("scheduled_days", sa.Float, server_default="0.0"),
        sa.Column("elapsed_days", sa.Float, server_default="0.0"),
    )
    op.create_index("idx_review_card", "card_reviews", ["card_id", "reviewed_at"])
    op.create_index("idx_review_student", "card_reviews", ["student_id", "reviewed_at"])


def downgrade() -> None:
    op.drop_table("card_reviews")
    op.drop_table("flashcard_cards")
    op.drop_table("flashcard_decks")
