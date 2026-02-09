#!/usr/bin/env python3
"""Register an LMS platform for LTI 1.3 launches.

Usage:
    python scripts/register_platform.py

Interactively prompts for platform details and inserts into lti_platforms table.
"""

import asyncio
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from docere.config import settings
from docere.models.lti_platform import LTIPlatform


CANVAS_DEFAULTS = {
    "auth_login_url_suffix": "/api/lti/authorize_redirect",
    "auth_token_url_suffix": "/login/oauth2/token",
    "jwks_url_suffix": "/api/lti/security/jwks",
}

MOODLE_DEFAULTS = {
    "auth_login_url_suffix": "/mod/lti/auth.php",
    "auth_token_url_suffix": "/mod/lti/token.php",
    "jwks_url_suffix": "/mod/lti/certs.php",
}


def prompt(label: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"  {label}{suffix}: ").strip()
    return value or default


async def main() -> None:
    print("\n=== Docere LTI 1.3 Platform Registration ===\n")

    # Platform type
    platform_type = ""
    while platform_type not in ("canvas", "moodle"):
        platform_type = prompt("Platform type (canvas/moodle)").lower()

    defaults = CANVAS_DEFAULTS if platform_type == "canvas" else MOODLE_DEFAULTS

    institution_name = prompt("Institution name (e.g. 'Springfield Middle School')")
    base_url = prompt("LMS base URL (e.g. 'https://canvas.school.edu')").rstrip("/")

    # LTI 1.3 registration details
    print("\n  --- LTI 1.3 Registration (from LMS Developer Keys) ---")
    issuer = prompt("Issuer", base_url)
    client_id = prompt("Client ID")
    deployment_id = prompt("Deployment ID")

    auth_login_url = prompt("Auth login URL", f"{base_url}{defaults['auth_login_url_suffix']}")
    auth_token_url = prompt("Auth token URL", f"{base_url}{defaults['auth_token_url_suffix']}")
    jwks_url = prompt("JWKS URL", f"{base_url}{defaults['jwks_url_suffix']}")

    # API credentials (optional, needed for course sync)
    print("\n  --- API Credentials (for course data sync) ---")
    api_base_url = prompt("API base URL", base_url)
    api_token = prompt("API token (Canvas Bearer / Moodle wstoken)")

    # Confirm
    print(f"\n  Platform: {platform_type} — {institution_name}")
    print(f"  Issuer: {issuer}")
    print(f"  Client ID: {client_id}")
    print(f"  JWKS URL: {jwks_url}")
    confirm = prompt("\n  Register this platform? (y/n)", "y")
    if confirm.lower() != "y":
        print("  Cancelled.")
        return

    # Insert into database
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as db:
        # Check for existing
        result = await db.execute(
            select(LTIPlatform).where(
                LTIPlatform.issuer == issuer,
                LTIPlatform.client_id == client_id,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            print(f"\n  Platform already registered (id: {existing.id}). Updating...")
            existing.deployment_id = deployment_id
            existing.auth_login_url = auth_login_url
            existing.auth_token_url = auth_token_url
            existing.jwks_url = jwks_url
            existing.platform_type = platform_type
            existing.institution_name = institution_name
            existing.api_base_url = api_base_url or None
            existing.api_token = api_token or None
            existing.is_active = True
            platform_id = existing.id
        else:
            platform = LTIPlatform(
                id=uuid.uuid4(),
                issuer=issuer,
                client_id=client_id,
                deployment_id=deployment_id,
                auth_login_url=auth_login_url,
                auth_token_url=auth_token_url,
                jwks_url=jwks_url,
                platform_type=platform_type,
                institution_name=institution_name,
                api_base_url=api_base_url or None,
                api_token=api_token or None,
            )
            db.add(platform)
            platform_id = platform.id

        await db.commit()

    await engine.dispose()

    print(f"\n  Registered! Platform ID: {platform_id}")
    print(f"\n  Configure your LMS with:")
    print(f"    OIDC Login URL:  {settings.app_base_url}/api/v1/auth/lti/login")
    print(f"    Launch URL:      {settings.app_base_url}/api/v1/auth/lti/launch")
    print(f"    Redirect URI:    {settings.app_base_url}/api/v1/auth/lti/launch")
    print()


if __name__ == "__main__":
    asyncio.run(main())
