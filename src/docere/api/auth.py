"""Authentication routes: LTI 1.3 launch, JWT tokens, dev login."""

import secrets
import uuid
from urllib.parse import urlencode

import jwt as pyjwt
from arq import create_pool
from arq.connections import RedisSettings
from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from docere.config import settings
from docere.dependencies import create_access_token, get_current_user_id, get_db, get_redis
from docere.models.lti_platform import LTIPlatform
from docere.models.user import User
from docere.services.jwks_cache import get_jwks_client
from docere.services.lti_service import (
    create_adapter,
    ensure_enrollment,
    extract_lti_claims,
    handle_lti_course,
    sync_user_enrollments,
    upsert_lti_user,
)

router = APIRouter()
logger = structlog.get_logger()


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


# ── LTI 1.3 Routes ──


async def _handle_lti_login(
    iss: str,
    login_hint: str,
    client_id: str,
    target_link_uri: str,
    lti_message_hint: str,
    lti_deployment_id: str,
    db: AsyncSession,
) -> RedirectResponse:
    """OIDC login initiation — Step 1 of LTI 1.3 launch.

    The LMS redirects here first. We look up the platform, generate
    state + nonce, store them in Redis, and redirect to the LMS
    authorization endpoint.
    """
    redis = get_redis()

    # Look up platform registration
    result = await db.execute(
        select(LTIPlatform).where(
            LTIPlatform.issuer == iss,
            LTIPlatform.client_id == client_id,
            LTIPlatform.is_active.is_(True),
        )
    )
    platform = result.scalar_one_or_none()

    if not platform:
        logger.warning("LTI login from unregistered platform", issuer=iss, client_id=client_id)
        raise HTTPException(status_code=403, detail="Unregistered platform")

    # Generate state and nonce for CSRF/replay protection
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)

    # Store in Redis with 10-minute TTL
    await redis.setex(f"lti:state:{state}", 600, f"{nonce}:{str(platform.id)}")

    # Build redirect to LMS authorization endpoint
    redirect_uri = f"{settings.app_base_url}/api/v1/auth/lti/launch"
    params = {
        "scope": "openid",
        "response_type": "id_token",
        "response_mode": "form_post",
        "client_id": platform.client_id,
        "redirect_uri": redirect_uri,
        "login_hint": login_hint,
        "state": state,
        "nonce": nonce,
        "prompt": "none",
    }
    if lti_message_hint:
        params["lti_message_hint"] = lti_message_hint

    auth_url = f"{platform.auth_login_url}?{urlencode(params)}"
    logger.info("LTI OIDC login redirect", issuer=iss, platform=platform.institution_name)
    return RedirectResponse(url=auth_url, status_code=302)


@router.get("/lti/login")
async def lti_login_get(
    iss: str = Query(..., description="Issuer (LMS instance URL)"),
    login_hint: str = Query(..., description="LMS user identifier"),
    client_id: str = Query(..., description="OAuth2 client ID"),
    target_link_uri: str = Query(..., description="Target resource link"),
    lti_message_hint: str = Query("", description="LMS message hint"),
    lti_deployment_id: str = Query("", description="Deployment ID"),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """OIDC login initiation via GET (some LMS use GET)."""
    return await _handle_lti_login(
        iss, login_hint, client_id, target_link_uri,
        lti_message_hint, lti_deployment_id, db,
    )


@router.post("/lti/login")
async def lti_login_post(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """OIDC login initiation via POST (Moodle sends form POST)."""
    form = await request.form()
    return await _handle_lti_login(
        iss=str(form["iss"]),
        login_hint=str(form["login_hint"]),
        client_id=str(form["client_id"]),
        target_link_uri=str(form["target_link_uri"]),
        lti_message_hint=str(form.get("lti_message_hint", "")),
        lti_deployment_id=str(form.get("lti_deployment_id", "")),
        db=db,
    )


@router.post("/lti/launch")
async def lti_launch(
    request: Request,
    id_token: str = Form(...),
    state: str = Form(...),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """LTI 1.3 launch endpoint — Step 2 of LTI 1.3 launch.

    Receives the signed JWT (id_token) from the LMS via form POST.
    Validates state, JWT signature (RS256 via JWKS), nonce, then
    upserts user, handles course, assigns study group, and redirects
    to the frontend with a Docere JWT.
    """
    redis = get_redis()

    # 1. Validate state from Redis
    state_value = await redis.getdel(f"lti:state:{state}")
    if not state_value:
        raise HTTPException(status_code=400, detail="Invalid or expired state parameter")

    expected_nonce, platform_id = state_value.split(":", 1)

    # 2. Look up platform
    platform = await db.get(LTIPlatform, uuid.UUID(platform_id))
    if not platform or not platform.is_active:
        raise HTTPException(status_code=403, detail="Platform not found or inactive")

    # 3. Validate JWT via JWKS (RS256)
    try:
        jwks_client = get_jwks_client(platform.jwks_url)
        signing_key = jwks_client.get_signing_key_from_jwt(id_token)

        claims = pyjwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=platform.client_id,
            issuer=platform.issuer,
            options={"require": ["sub", "iss", "aud", "exp", "iat", "nonce"]},
        )
    except pyjwt.InvalidTokenError as e:
        logger.warning("LTI JWT validation failed", error=str(e))
        raise HTTPException(status_code=401, detail=f"Invalid LTI token: {e}")

    # 4. Validate nonce (replay protection)
    token_nonce = claims.get("nonce")
    if token_nonce != expected_nonce:
        raise HTTPException(status_code=400, detail="Nonce mismatch")

    # 5. Check nonce hasn't been reused (store in Redis for token lifetime)
    nonce_key = f"lti:nonce:{token_nonce}"
    was_set = await redis.set(nonce_key, "1", nx=True, ex=3600)
    if not was_set:
        raise HTTPException(status_code=400, detail="Nonce already used")

    # 6. Extract claims and process launch
    lti_data = extract_lti_claims(claims, platform)

    user = await upsert_lti_user(db, lti_data, platform)

    course, is_new_course = await handle_lti_course(db, lti_data, platform, user)

    if course:
        enrollment = await ensure_enrollment(db, user, course, lti_role=lti_data.role)

    # Discover and sync enrollments for the user's other LMS courses
    # so all their courses show up immediately, not just the launched one
    if platform.api_base_url and platform.api_token:
        try:
            adapter = create_adapter(platform)
            await sync_user_enrollments(db, user, adapter, platform)
        except Exception:
            logger.warning("Cross-course enrollment sync failed", user_id=str(user.id))

    await db.commit()

    # 7. Enqueue sync tasks (don't block the redirect)
    if course and platform.api_base_url and platform.api_token:
        try:
            redis_settings = RedisSettings.from_dsn(settings.redis_url)
            pool = await create_pool(redis_settings)

            if is_new_course:
                # Full sync for brand-new courses
                await pool.enqueue_job(
                    "run_lti_course_sync",
                    str(platform.id),
                    str(course.id),
                    lti_data.external_course_id,
                )
                logger.info("Enqueued course sync", course_id=str(course.id))
            else:
                # Lightweight material-only sync on every launch
                await pool.enqueue_job(
                    "run_lti_material_sync",
                    str(platform.id),
                    str(course.id),
                    lti_data.external_course_id,
                )
                logger.info("Enqueued material sync", course_id=str(course.id))

            await pool.aclose()
        except Exception:
            logger.exception("Failed to enqueue sync")

    # 8. Create Docere JWT and redirect to frontend
    token = create_access_token(user.id, role=user.role)

    # Use hash fragment to avoid server logging of tokens
    fragment = urlencode({
        "token": token,
        "user_id": str(user.id),
        "name": user.name,
        "role": user.role,
        "course_id": str(course.id) if course else "",
    })

    # Route instructors to the dashboard, students to the chat
    if user.role in ("instructor", "admin", "ta") and course:
        redirect_url = f"{settings.frontend_url}/instructor/dashboard/{course.id}#{fragment}"
    else:
        redirect_url = f"{settings.frontend_url}/lti/callback#{fragment}"

    logger.info(
        "LTI launch complete",
        user_id=str(user.id),
        course_id=str(course.id) if course else None,
        platform=platform.institution_name,
    )
    return RedirectResponse(url=redirect_url, status_code=303)


# ── Standard Auth Routes ──


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
