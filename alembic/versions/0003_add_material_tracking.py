"""add external_lms_id and content_hash to course_materials

Revision ID: 0003
Revises: 0002
Create Date: 2026-02-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("course_materials", sa.Column("external_lms_id", sa.String(255)))
    op.add_column("course_materials", sa.Column("content_hash", sa.String(64)))
    op.create_index(
        "idx_course_material_lms_id",
        "course_materials",
        ["course_id", "external_lms_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_course_material_lms_id")
    op.drop_column("course_materials", "content_hash")
    op.drop_column("course_materials", "external_lms_id")
