"""Authentication routes: LTI 1.3 launch and JWT tokens."""

from fastapi import APIRouter

router = APIRouter()


@router.post("/lti/launch")
async def lti_launch() -> dict[str, str]:
    """LTI 1.3 launch endpoint - receives launch from Canvas/Moodle."""
    # TODO: Validate LTI launch, create/update user, auto-sync course, return JWT
    return {"status": "not_implemented"}


@router.get("/me")
async def get_current_user() -> dict[str, str]:
    """Get current authenticated user from JWT."""
    # TODO: Decode JWT, return user info
    return {"status": "not_implemented"}


@router.post("/token/refresh")
async def refresh_token() -> dict[str, str]:
    """Refresh JWT token."""
    # TODO: Validate refresh token, issue new JWT
    return {"status": "not_implemented"}
