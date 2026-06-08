"""Rate limiting middleware using Redis sliding window.

Three tiers:
  - LLM endpoints (POST to /chat/.../messages, /query): 20 req/min per user
  - Read endpoints (everything else): 60 req/min per user
  - Auth endpoints (/auth): 10 req/min per IP (prevents brute force)

Keyed by user ID (from JWT) when authenticated, IP address otherwise.
"""

import time

import jwt
import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from docere.config import settings

logger = structlog.get_logger()

# ── Tier definitions ──

# Auth paths get IP-based limits (brute force protection)
_AUTH_PATHS = ("/auth/",)

# Tier: (max_requests, window_seconds)
TIER_LLM = (20, 60)
TIER_READ = (60, 60)
TIER_AUTH = (10, 60)


def _classify_tier(path: str, method: str = "GET") -> tuple[int, int]:
    """Determine rate limit tier from request path and method.

    Only POST requests that trigger LLM calls get the strict LLM tier.
    GET requests on /chat/ (list conversations, get history) use the read tier.
    """
    for p in _AUTH_PATHS:
        if p in path:
            return TIER_AUTH
    # LLM tier: only expensive POST endpoints that invoke Claude
    if method == "POST" and ("/messages" in path or "/query" in path):
        return TIER_LLM
    return TIER_READ


def _extract_user_id(request: Request) -> str | None:
    """Try to extract user ID from JWT bearer token (best-effort, no validation)."""
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth[7:]
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={"verify_exp": False},
        )
        return payload.get("sub")
    except Exception:
        return None


def _get_client_ip(request: Request) -> str:
    """Get client IP, respecting X-Forwarded-For behind a proxy."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Redis-backed sliding window rate limiter."""

    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip health check and static paths
        path = request.url.path
        if path in ("/health", "/docs", "/openapi.json"):
            return await call_next(request)

        # Determine tier
        max_requests, window = _classify_tier(path, request.method)

        # Determine identifier
        is_auth_path = any(p in path for p in _AUTH_PATHS)
        if is_auth_path:
            identifier = f"ip:{_get_client_ip(request)}"
        else:
            user_id = _extract_user_id(request)
            identifier = f"user:{user_id}" if user_id else f"ip:{_get_client_ip(request)}"

        # Build Redis key with time window
        window_key = int(time.time()) // window
        redis_key = f"rate:{identifier}:{path_tier(path)}:{window_key}"

        # Check rate limit via Redis
        try:
            from docere.dependencies import get_redis

            redis = get_redis()
            current = await redis.incr(redis_key)
            if current == 1:
                await redis.expire(redis_key, window)
        except RuntimeError:
            # Redis not initialized (e.g., in tests) — allow request
            return await call_next(request)
        except Exception as e:
            # Redis down — fail open (allow request, log warning)
            logger.warning("Rate limit check failed, allowing request", error=str(e))
            return await call_next(request)

        # Set rate limit headers
        response = None
        if current > max_requests:
            response = JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded. Please slow down.",
                    "retry_after": window,
                },
            )
            logger.warning(
                "Rate limit exceeded",
                identifier=identifier,
                path=path,
                current=current,
                limit=max_requests,
            )
        else:
            response = await call_next(request)

        response.headers["X-RateLimit-Limit"] = str(max_requests)
        response.headers["X-RateLimit-Remaining"] = str(max(0, max_requests - current))
        response.headers["X-RateLimit-Reset"] = str((window_key + 1) * window)

        return response


def path_tier(path: str) -> str:
    """Return tier name for Redis key partitioning."""
    for p in _AUTH_PATHS:
        if p in path:
            return "auth"
    if "/messages" in path or "/query" in path:
        return "llm"
    return "read"
