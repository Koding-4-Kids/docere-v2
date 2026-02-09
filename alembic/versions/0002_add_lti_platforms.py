"""add lti_platforms table

Revision ID: 0002
Revises: 0001
Create Date: 2026-02-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "lti_platforms",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        # LTI 1.3 registration
        sa.Column("issuer", sa.String(500), nullable=False),
        sa.Column("client_id", sa.String(255), nullable=False),
        sa.Column("deployment_id", sa.String(255), nullable=False),
        sa.Column("auth_login_url", sa.String(1000), nullable=False),
        sa.Column("auth_token_url", sa.String(1000), nullable=False),
        sa.Column("jwks_url", sa.String(1000), nullable=False),
        # Platform metadata
        sa.Column("platform_type", sa.String(50), nullable=False),
        sa.Column("institution_name", sa.String(500), nullable=False),
        # API credentials for data sync
        sa.Column("api_base_url", sa.String(1000)),
        sa.Column("api_token", sa.Text),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        # Timestamps
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        # Unique constraint
        sa.UniqueConstraint("issuer", "client_id", name="uq_lti_platform_issuer_client"),
    )
    # Index for fast OIDC lookup during login initiation
    op.create_index("idx_lti_platform_issuer_active", "lti_platforms", ["issuer", "is_active"])


def downgrade() -> None:
    op.drop_index("idx_lti_platform_issuer_active")
    op.drop_table("lti_platforms")
