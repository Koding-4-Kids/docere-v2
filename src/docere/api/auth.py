"""Authentication routes: LTI 1.3 launch, JWT tokens, dev login."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from docere.dependencies import create_access_token, get_current_user_id, get_db
from docere.models.user import User

router = APIRouter()


# ── Schemas ──


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: uuid.UUID
    name: str
    role: str


class UserResponse(BaseModel):
    id: uuid.UUID
    name: str
    email: str | None
    role: str

    model_config = {"from_attributes": True}


class DevLoginRequest(BaseModel):
    """For development only — login by email without password."""
    email: str


# ── Routes ──


@router.post("/lti/launch", response_model=TokenResponse)
async def lti_launch() -> dict[str, str]:
    """LTI 1.3 launch endpoint - receives launch from Canvas/Moodle.

    TODO: Validate LTI JWT, extract user claims, create/update user,
    auto-sync course on first launch, return Docere JWT.
    """
    raise HTTPException(status_code=501, detail="LTI 1.3 launch not yet implemented")


@router.post("/dev/login", response_model=TokenResponse)
async def dev_login(
    request: DevLoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Development-only login: find or create user by email, return JWT.

    This endpoint exists so the frontend can authenticate during development
    without a full LTI flow. Should be disabled in production.
    """
    result = await db.execute(
        select(User).where(User.email == request.email)
    )
    user = result.scalar_one_or_none()

    if not user:
        # Auto-create dev user
        user = User(
            name=request.email.split("@")[0].replace(".", " ").title(),
            email=request.email,
            role="student",
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    token = create_access_token(user.id, role=user.role)

    return TokenResponse(
        access_token=token,
        user_id=user.id,
        name=user.name,
        role=user.role,
    )


@router.get("/me", response_model=UserResponse)
async def get_me(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Get current authenticated user from JWT."""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.post("/token/refresh", response_model=TokenResponse)
async def refresh_token(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Refresh JWT token — issues a new token with fresh expiration."""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    token = create_access_token(user.id, role=user.role)

    return TokenResponse(
        access_token=token,
        user_id=user.id,
        name=user.name,
        role=user.role,
    )
