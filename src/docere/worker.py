"""ARQ background worker: processes async tasks via Redis queue.

Tasks:
- strategy_evolution: Weekly mutation/pruning of teaching strategies
- memory_compression: Weekly compression of old memory records
- lms_sync: Periodic LMS course sync (every 2 hours)

Run with: arq docere.worker.WorkerSettings
"""

from arq import cron
from arq.connections import RedisSettings
import structlog

from docere.config import settings
from docere.dependencies import async_session, init_clients, get_qdrant, get_claude

logger = structlog.get_logger()


# ── Task definitions ──


async def run_strategy_evolution(ctx: dict) -> dict:
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


async def run_memory_compression(ctx: dict) -> dict:
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


async def run_lms_sync(ctx: dict) -> dict:
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


async def run_seed_strategies(ctx: dict) -> dict:
    """One-time: seed the strategy archive if empty."""
    from docere.core.improvement.strategy_archive import StrategyArchive

    async with async_session() as db:
        archive = StrategyArchive(db)
        count = await archive.seed_strategies()
        await db.commit()

    logger.info("Strategy seeding complete", seeded=count)
    return {"seeded": count}


async def run_lti_course_sync(
    ctx: dict,
    platform_id: str,
    course_id: str,
    external_course_id: str,
) -> dict:
    """Background: full sync for a course after first LTI launch.

    Uses per-platform API credentials from lti_platforms table.
    """
    import uuid
    from docere.models.lti_platform import LTIPlatform
    from docere.services.lti_service import create_adapter
    from docere.services.lms_sync_service import LMSSyncService

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

    logger.info(
        "LTI course sync complete",
        course_id=course_id,
        platform=platform.institution_name,
    )
    return {"course_id": course_id, "status": "synced"}


# ── Worker lifecycle ──


async def startup(ctx: dict) -> None:
    """Initialize shared clients when the worker starts."""
    init_clients()
    logger.info("ARQ worker started")


async def shutdown(ctx: dict) -> None:
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
