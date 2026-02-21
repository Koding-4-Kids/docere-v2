"""CSP middleware: dynamic frame-ancestors for LMS iframe embedding."""

import time

from sqlalchemy import select
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
import structlog

from docere.config import settings
from docere.dependencies import async_session
from docere.models.lti_platform import LTIPlatform

logger = structlog.get_logger()

_issuer_cache: list[str] = []
_cache_time: float = 0
_CACHE_TTL = 300  # 5 minutes


async def _get_cached_issuers() -> list[str]:
    """Return cached list of active LTI platform issuer URLs."""
    global _issuer_cache, _cache_time

    if time.time() - _cache_time < _CACHE_TTL and _issuer_cache:
        return _issuer_cache

    try:
        async with async_session() as db:
            result = await db.execute(
                select(LTIPlatform.issuer).where(LTIPlatform.is_active.is_(True))
            )
            _issuer_cache = list({row[0] for row in result.all() if row[0]})
            _cache_time = time.time()
    except Exception:
        logger.debug("CSP issuer cache refresh failed, using stale cache")

    return _issuer_cache


class CSPMiddleware(BaseHTTPMiddleware):
    """Sets Content-Security-Policy frame-ancestors from registered LTI platforms."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        issuers = await _get_cached_issuers()
        ancestors = ["'self'"]
        ancestors.extend(issuers)

        if settings.debug:
            ancestors.append("http://localhost:*")
            ancestors.append("http://127.0.0.1:*")

        response.headers["Content-Security-Policy"] = (
            f"frame-ancestors {' '.join(ancestors)}"
        )
        return response
