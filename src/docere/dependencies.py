"""FastAPI dependency injection: database sessions, auth, shared clients."""

import uuid
from collections.abc import AsyncGenerator

import jwt
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


def create_access_token(user_id: uuid.UUID, role: str = "student") -> str:
    """Create a JWT access token for a user."""
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expiration_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
