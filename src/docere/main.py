"""FastAPI application entry point."""

import os
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import structlog

from docere.config import settings
from docere.api import (
    auth,
    calendar,
    chat,
    courses,
    students,
    instructor,
    memory,
    analytics,
    lms,
    integrations,
    gradebook_sync,
    flashcards,
    documents,
)
from docere.dependencies import engine, init_clients, get_qdrant, init_redis, shutdown_redis
from docere.middleware.csp import CSPMiddleware
from docere.middleware.rate_limit import RateLimitMiddleware

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Application startup and shutdown events."""
    logger.info("Starting Docere v2", environment=settings.environment)

    # Validate critical secrets
    if not settings.jwt_secret:
        if settings.environment == "development":
            logger.warning("JWT_SECRET not set — using insecure dev default")
            settings.jwt_secret = "dev-secret-do-not-use-in-prod"
        else:
            raise RuntimeError("JWT_SECRET must be set in production")

    # Initialize shared clients (Claude, Qdrant, Redis)
    try:
        init_clients()
        logger.info("Claude and Qdrant clients initialized")
    except Exception as e:
        logger.error(
            "Failed to initialize LLM/vector clients — app will not function", error=str(e)
        )
        raise

    try:
        await init_redis()
        logger.info("Redis connected")
    except Exception as e:
        logger.warning("Redis connection failed — rate limiting disabled", error=str(e))

    # Ensure Qdrant collections exist
    try:
        qdrant = get_qdrant()
        await qdrant.ensure_collection("interactions_default")
        await qdrant.ensure_collection("materials_default")
    except Exception as e:
        logger.warning("Qdrant collection setup failed — vector search may not work", error=str(e))

    logger.info("All services initialized")
    yield

    # Shutdown: close connections
    await shutdown_redis()
    await engine.dispose()
    logger.info("Shutting down Docere v2")


app = FastAPI(
    title="Docere v2",
    description="Memory-augmented, self-improving learning agent for LMS integration",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(RateLimitMiddleware)
app.add_middleware(CSPMiddleware)

# CORS: in debug, allow everything; in prod, allow the configured frontend URL
_cors_origins = ["*"] if settings.debug else [settings.frontend_url, settings.app_base_url]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(chat.router, prefix="/api/v1/chat", tags=["chat"])
app.include_router(courses.router, prefix="/api/v1/courses", tags=["courses"])
app.include_router(students.router, prefix="/api/v1/students", tags=["students"])
app.include_router(instructor.router, prefix="/api/v1/instructor", tags=["instructor"])
app.include_router(memory.router, prefix="/api/v1/memory", tags=["memory"])
app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["analytics"])
app.include_router(lms.router, prefix="/api/v1/lms", tags=["lms"])
app.include_router(calendar.router, prefix="/api/v1/calendar", tags=["calendar"])
app.include_router(integrations.router, prefix="/api/v1/integrations", tags=["integrations"])
app.include_router(gradebook_sync.router, prefix="/api/v1/gradebook", tags=["gradebook"])
app.include_router(flashcards.router, prefix="/api/v1/flashcards", tags=["flashcards"])
app.include_router(documents.router, prefix="/api/v1/documents", tags=["documents"])


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "version": "0.1.0"}


# Serve built frontend (must be AFTER API routes so /api/* takes priority)
# Check multiple locations: relative to source, relative to CWD, env override
_frontend_candidates = [
    Path(os.environ.get("FRONTEND_DIST_DIR", "")),  # explicit override
    Path(__file__).resolve().parent.parent.parent
    / "frontend"
    / "dist",  # dev: src/docere/../../frontend/dist
    Path("frontend/dist"),  # docker: /app/frontend/dist
]
for _candidate in _frontend_candidates:
    if _candidate.is_dir():
        app.mount("/", StaticFiles(directory=str(_candidate), html=True), name="frontend")
        logger.info("Serving frontend from %s", _candidate)
        break
