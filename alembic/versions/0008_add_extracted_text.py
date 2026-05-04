"""Add extracted_text column to student_documents.

Revision ID: 0008
Revises: 0007
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column("student_documents", sa.Column("extracted_text", sa.Text, nullable=True))


def downgrade() -> None:
    op.drop_column("student_documents", "extracted_text")
