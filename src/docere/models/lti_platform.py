"""LTI platform registration model for multi-tenant LMS integration."""

from sqlalchemy import Boolean, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from docere.models.base import Base, TimestampMixin, UUIDMixin


class LTIPlatform(Base, UUIDMixin, TimestampMixin):
    """Registered LMS platform for LTI 1.3 launches.

    Each institution's Canvas/Moodle instance is a separate row,
    replacing the single-tenant env var approach.
    """

    __tablename__ = "lti_platforms"
    __table_args__ = (
        UniqueConstraint("issuer", "client_id", name="uq_lti_platform_issuer_client"),
    )

    # LTI 1.3 registration fields
    issuer: Mapped[str] = mapped_column(String(500), nullable=False)
    client_id: Mapped[str] = mapped_column(String(255), nullable=False)
    deployment_id: Mapped[str] = mapped_column(String(255), nullable=False)
    auth_login_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    auth_token_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    jwks_url: Mapped[str] = mapped_column(String(1000), nullable=False)

    # Platform metadata
    platform_type: Mapped[str] = mapped_column(String(50), nullable=False)  # "canvas" or "moodle"
    institution_name: Mapped[str] = mapped_column(String(500), nullable=False)

    # API credentials for data sync (per-platform)
    api_base_url: Mapped[str | None] = mapped_column(String(1000))
    api_token: Mapped[str | None] = mapped_column(Text)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
