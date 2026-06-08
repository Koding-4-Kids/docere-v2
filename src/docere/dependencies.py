"""FastAPI dependency injection: database sessions, auth, shared clients."""

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC

import jwt
import redis.asyncio as aioredis
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from docere.config import settings
from docere.integrations.llm.client import ClaudeClient
from docere.integrations.vector_db.qdrant import QdrantStore

# ── Database ──

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_size=10,
    max_overflow=20,
)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield a database session."""
    async with async_session() as session:
        yield session


# ── Shared clients (initialized once on startup via lifespan) ──

_qdrant: QdrantStore | None = None
_claude: ClaudeClient | None = None


def init_clients() -> None:
    """Initialize shared clients. Called once during app startup."""
    global _qdrant, _claude
    _qdrant = QdrantStore()
    _claude = ClaudeClient()


def get_qdrant() -> QdrantStore:
    """Get the shared Qdrant client."""
    if _qdrant is None:
        raise RuntimeError("Qdrant client not initialized — app lifespan not started")
    return _qdrant


def get_claude() -> ClaudeClient:
    """Get the shared Claude client."""
    if _claude is None:
        raise RuntimeError("Claude client not initialized — app lifespan not started")
    return _claude


# ── Redis ──

_redis: aioredis.Redis | None = None


async def init_redis() -> None:
    """Initialize the async Redis client. Called once during app startup."""
    global _redis
    _redis = aioredis.from_url(settings.redis_url, decode_responses=True)


def get_redis() -> aioredis.Redis:
    """Get the shared async Redis client."""
    if _redis is None:
        raise RuntimeError("Redis client not initialized — app lifespan not started")
    return _redis


async def shutdown_redis() -> None:
    """Close the Redis connection pool."""
    global _redis
    if _redis:
        await _redis.aclose()
        _redis = None


# ── JWT Auth ──

_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> uuid.UUID:
    """Extract and validate user ID from JWT bearer token.

    Returns the user's UUID. Raises 401 if token is missing/invalid/expired.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing subject",
            )
        return uuid.UUID(user_id)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        )
    except (jwt.InvalidTokenError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        )


async def get_current_user_role(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> tuple[uuid.UUID, str]:
    """Extract user ID and role from JWT bearer token."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        user_id = payload.get("sub")
        role = payload.get("role", "student")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing subject",
            )
        return uuid.UUID(user_id), role
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        )
    except (jwt.InvalidTokenError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        )


async def require_instructor(
    user_data: tuple[uuid.UUID, str] = Depends(get_current_user_role),
) -> uuid.UUID:
    """Ensure the caller is an instructor, TA, or admin. Returns user_id."""
    user_id, role = user_data
    if role not in ("instructor", "ta", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Instructor access required",
        )
    return user_id


def create_access_token(user_id: uuid.UUID, role: str = "student") -> str:
    """Create a JWT access token for a user."""
    from datetime import datetime, timedelta

    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expiration_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
