"""ARQ background worker: processes async tasks via Redis queue.

Tasks:
- strategy_evolution: Weekly mutation/pruning of teaching strategies
- memory_compression: Weekly compression of old memory records
- lms_sync: Periodic LMS course sync (every 2 hours)

Run with: arq docere.worker.WorkerSettings
"""

from datetime import UTC
from typing import Any

import structlog
from arq import cron
from arq.connections import RedisSettings

from docere.config import settings
from docere.dependencies import async_session, get_claude, get_qdrant, init_clients

logger = structlog.get_logger()


# ── Task definitions ──


async def run_strategy_evolution(ctx: dict[str, Any]) -> dict[str, Any]:
    """Weekly: evolve teaching strategies based on accumulated scores.

    Mutates top performers and prunes strategies with low scores.
    This is the core self-improvement mechanism.
    """
    from docere.core.improvement.strategy_evolver import StrategyEvolver

    async with async_session() as db:
        evolver = StrategyEvolver(db, get_claude())
        result = await evolver.evolve()
        await db.commit()

    logger.info("Strategy evolution task complete", **result)
    return result


async def run_memory_compression(ctx: dict[str, Any]) -> dict[str, Any]:
    """Weekly: compress old memory records to save context window space.

    Groups old interactions by type/course and generates concise summaries.
    """
    from docere.core.memory.compressor import MemoryCompressor

    async with async_session() as db:
        compressor = MemoryCompressor(db, get_claude(), get_qdrant())
        compressed = await compressor.compress_all()
        await db.commit()

    logger.info("Memory compression task complete", compressed=compressed)
    return {"compressed": compressed}


async def run_lms_sync(ctx: dict[str, Any]) -> dict[str, Any]:
    """Every 2 hours: sync grades and assignments from Canvas/Moodle.

    After syncing, processes grade changes through OutcomeTracker
    (links grades to interaction scores) and MemoryLayer (creates
    grade memory records for the agent).
    """
    from docere.tasks.lms_sync import sync_all_courses

    async with async_session() as db:
        result = await sync_all_courses(db, claude=get_claude(), qdrant=get_qdrant())
        await db.commit()

    logger.info("LMS sync task complete", **result)
    return result


async def run_seed_strategies(ctx: dict[str, Any]) -> dict[str, Any]:
    """One-time: seed the strategy archive if empty."""
    from docere.core.improvement.strategy_archive import StrategyArchive

    async with async_session() as db:
        archive = StrategyArchive(db)
        count = await archive.seed_strategies()
        await db.commit()

    logger.info("Strategy seeding complete", seeded=count)
    return {"seeded": count}


async def run_lti_course_sync(
    ctx: dict[str, Any],
    platform_id: str,
    course_id: str,
    external_course_id: str,
) -> dict[str, Any]:
    """Background: full sync for a course after first LTI launch.

    Uses per-platform API credentials from lti_platforms table.
    After sync, embeds all materials + syllabus into Qdrant.
    """
    import uuid

    from sqlalchemy import select

    from docere.core.memory.teacher_context import TeacherContextManager
    from docere.models.course import CourseMaterial
    from docere.models.lti_platform import LTIPlatform
    from docere.services.lms_sync_service import LMSSyncService
    from docere.services.lti_service import create_adapter

    async with async_session() as db:
        platform = await db.get(LTIPlatform, uuid.UUID(platform_id))
        if not platform:
            logger.error("Platform not found for LTI sync", platform_id=platform_id)
            return {"error": "platform_not_found"}

        adapter = create_adapter(platform)
        lms_platform = str(platform.id)

        sync_service = LMSSyncService(db, adapter)
        course = await sync_service.full_sync(external_course_id, lms_platform)
        await db.commit()

        # Embed all synced materials + syllabus into Qdrant
        try:
            qdrant = get_qdrant()
            claude = get_claude()
            ctx_manager = TeacherContextManager(qdrant, claude)

            result = await db.execute(
                select(CourseMaterial).where(
                    CourseMaterial.course_id == course.id,
                    CourseMaterial.content.isnot(None),
                )
            )
            materials = result.scalars().all()

            materials_data = [
                {
                    "title": m.title or "",
                    "content": m.content or "",
                    "type": m.material_type,
                }
                for m in materials
                if m.content and len(m.content.strip()) >= 50
            ]

            chunks = await ctx_manager.ingest_course(
                course_id=str(course.id),
                syllabus=course.syllabus_text,
                materials=materials_data,
            )

            # Mark materials as embedded
            for m in materials:
                if m.content and len(m.content.strip()) >= 50:
                    m.embedding_id = f"materials_{course.id}"
            await db.commit()

            logger.info(
                "Initial material embedding complete",
                course_id=course_id,
                chunks=chunks,
            )
        except Exception:
            logger.exception("Failed to embed materials after first sync")

    logger.info(
        "LTI course sync complete",
        course_id=course_id,
        platform=platform.institution_name,
    )
    return {"course_id": course_id, "status": "synced"}


async def run_lti_material_sync(
    ctx: dict[str, Any],
    platform_id: str,
    course_id: str,
    external_course_id: str,
) -> dict[str, Any]:
    """Background: lightweight material-only sync on every LTI launch.

    Only syncs materials (not full course), so it's fast. Embeds any
    new/updated materials afterward.
    """
    import uuid

    from docere.models.course import Course
    from docere.models.lti_platform import LTIPlatform
    from docere.services.lms_sync_service import LMSSyncService
    from docere.services.lti_service import create_adapter
    from docere.tasks.lms_sync import _embed_new_materials

    new_count = 0
    updated_count = 0
    embedded = 0

    async with async_session() as db:
        platform = await db.get(LTIPlatform, uuid.UUID(platform_id))
        if not platform:
            logger.error("Platform not found for material sync", platform_id=platform_id)
            return {"error": "platform_not_found"}

        adapter = create_adapter(platform)
        sync_service = LMSSyncService(db, adapter)

        course = await db.get(Course, uuid.UUID(course_id))
        if not course:
            logger.error("Course not found for material sync", course_id=course_id)
            return {"error": "course_not_found"}

        # Pull and sync materials only
        from docere.integrations.lms.base import LMSCourse, LMSFullSync

        materials = await adapter.get_course_materials(external_course_id)
        sync_data = LMSFullSync(
            course=LMSCourse(
                external_id=external_course_id,
                name=course.name,
                course_code=course.course_code or "",
            ),
            materials=materials,
        )
        new_count, updated_count = await sync_service._sync_materials(course, sync_data)
        await db.commit()

        # Embed new/updated materials
        if new_count > 0 or updated_count > 0:
            try:
                embedded = await _embed_new_materials(db, course, get_qdrant(), get_claude())
                await db.commit()
            except Exception:
                logger.exception("Failed to embed materials after sync")

    logger.info(
        "LTI material sync complete",
        course_id=course_id,
        new=new_count,
        updated=updated_count,
        embedded=embedded,
    )
    return {
        "course_id": course_id,
        "new_materials": new_count,
        "updated_materials": updated_count,
        "embedded": embedded,
    }


async def run_document_ingestion(
    ctx: dict[str, Any],
    doc_id: str,
    file_path: str,
    student_id: str,
    course_id: str,
) -> dict[str, Any]:
    """Background: parse, chunk, embed, and store a student-uploaded document."""
    import os
    import shutil
    from datetime import datetime

    from docere.core.memory.student_documents import StudentDocumentManager
    from docere.models.document import StudentDocument

    async with async_session() as db:
        doc = await db.get(StudentDocument, __import__("uuid").UUID(doc_id))
        if not doc:
            logger.error("Document not found for ingestion", doc_id=doc_id)
            return {"error": "not_found"}

        doc.status = "processing"
        doc.processing_started_at = datetime.now(UTC)
        await db.commit()

        try:
            manager = StudentDocumentManager(get_qdrant())
            chunk_count, page_count = await manager.ingest_document(
                doc_id, file_path, student_id, course_id
            )
            doc.status = "completed"
            doc.chunk_count = chunk_count
            doc.page_count = page_count
            doc.processing_completed_at = datetime.now(UTC)
        except Exception as e:
            logger.error("Document ingestion failed", doc_id=doc_id, error=str(e))
            doc.status = "failed"
            doc.error_message = str(e)[:500]

        await db.commit()

    # Clean up temp file
    try:
        upload_dir = os.path.dirname(file_path)
        if os.path.isdir(upload_dir):
            shutil.rmtree(upload_dir)
    except Exception:
        pass

    logger.info(
        "Document ingestion task complete",
        doc_id=doc_id,
        status=doc.status,
        chunks=doc.chunk_count,
    )
    return {"doc_id": doc_id, "status": doc.status, "chunks": doc.chunk_count}


# ── Worker lifecycle ──


async def startup(ctx: dict[str, Any]) -> None:
    """Initialize shared clients when the worker starts."""
    init_clients()
    logger.info("ARQ worker started")


async def shutdown(ctx: dict[str, Any]) -> None:
    """Clean up when the worker stops."""
    logger.info("ARQ worker shutting down")


# ── ARQ settings ──


class WorkerSettings:
    """ARQ worker configuration."""

    redis_settings = RedisSettings.from_dsn(settings.redis_url)

    # Register task functions
    functions = [
        run_strategy_evolution,
        run_memory_compression,
        run_lms_sync,
        run_seed_strategies,
        run_lti_course_sync,
        run_lti_material_sync,
        run_document_ingestion,
    ]

    # Scheduled cron jobs
    cron_jobs = [
        # LMS grade sync: every 2 hours
        cron(run_lms_sync, hour={0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22}, minute={15}),
        # Strategy evolution: every Sunday at 3 AM
        cron(run_strategy_evolution, weekday={6}, hour={3}, minute={0}),
        # Memory compression: every Saturday at 4 AM
        cron(run_memory_compression, weekday={5}, hour={4}, minute={0}),
    ]

    on_startup = startup
    on_shutdown = shutdown

    # Worker config
    max_jobs = 5
    job_timeout = 600  # 10 minutes max per job
