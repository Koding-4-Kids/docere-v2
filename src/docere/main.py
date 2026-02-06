"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import structlog

from docere.config import settings
from docere.api import auth, chat, courses, students, instructor, memory, analytics, lms

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Application startup and shutdown events."""
    logger.info("Starting Docere v2", environment=settings.environment)
    # TODO: Initialize database connection pool
    # TODO: Initialize Qdrant client
    # TODO: Initialize Redis connection
    yield
    logger.info("Shutting down Docere v2")
    # TODO: Close connections


app = FastAPI(
    title="Docere v2",
    description="Memory-augmented, self-improving learning agent for LMS integration",
    version="0.1.0",
    lifespan=lifespan,
)

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


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "version": "0.1.0"}
