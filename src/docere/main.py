"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import structlog

from docere.config import settings
from docere.api import auth, calendar, chat, courses, students, instructor, memory, analytics, lms, integrations, gradebook_sync, flashcards
from docere.dependencies import engine, init_clients, get_qdrant, init_redis, shutdown_redis
from docere.middleware.csp import CSPMiddleware
from docere.middleware.rate_limit import RateLimitMiddleware

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Application startup and shutdown events."""
    logger.info("Starting Docere v2", environment=settings.environment)

    # Initialize shared clients (Claude, Qdrant, Redis)
    init_clients()
    await init_redis()

    # Ensure Qdrant collections exist
    qdrant = get_qdrant()
    await qdrant.ensure_collection("interactions_default")
    await qdrant.ensure_collection("materials_default")

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
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.debug else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
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


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "version": "0.1.0"}
