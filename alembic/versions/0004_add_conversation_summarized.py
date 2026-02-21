"""add summarized flag to conversations

Revision ID: 0004
Revises: 0003
Create Date: 2026-02-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Column may already exist (was added manually before this migration existed)
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = 'conversations' AND column_name = 'summarized'"
        )
    )
    if not result.fetchone():
        op.add_column(
            "conversations",
            sa.Column("summarized", sa.Boolean(), server_default="false", nullable=False),
        )


def downgrade() -> None:
    op.drop_column("conversations", "summarized")
