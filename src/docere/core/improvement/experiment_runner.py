"""Experiment runner: manages ablation study configuration and feature gating."""

import hashlib
from typing import Any, cast

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from docere.models.course import Enrollment
from docere.models.research import ResearchEvent, StudyConfig

logger = structlog.get_logger()

STUDY_GROUPS = ["control", "treatment_memory", "treatment_full"]


class ExperimentRunner:
    """Manages the ablation study and tracks research events."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_active_study(self, course_id: str) -> StudyConfig | None:
        """Get the active study configuration for a course."""
        result = await self.db.execute(
            select(StudyConfig).where(
                StudyConfig.course_id == course_id,
                StudyConfig.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()

    async def assign_student_group(
        self,
        student_id: str,
        course_id: str,
    ) -> str | None:
        """Assign a student to a study group using deterministic hashing.

        Uses the study's randomization_seed + student_id for reproducible
        but random-looking assignment. Returns the group name or None
        if no active study.
        """
        # Check if already assigned
        result = await self.db.execute(
            select(Enrollment).where(
                Enrollment.user_id == student_id,
                Enrollment.course_id == course_id,
            )
        )
        enrollment = result.scalar_one_or_none()
        if not enrollment:
            return None

        if enrollment.study_group:
            return enrollment.study_group

        # Get active study
        study = await self.get_active_study(course_id)
        if not study:
            return None

        # Deterministic assignment via hash
        seed = study.randomization_seed or 42
        hash_input = f"{seed}:{student_id}"
        hash_val = int(hashlib.sha256(hash_input.encode()).hexdigest(), 16)

        groups = study.groups.get("arms", STUDY_GROUPS)
        group = groups[hash_val % len(groups)]

        enrollment.study_group = group
        await self.db.flush()

        # Log assignment event
        await self.log_event(
            study_id=str(study.id),
            student_id=student_id,
            event_type="group_assignment",
            event_data={"group": group, "seed": seed},
        )

        logger.info(
            "Student assigned to study group",
            student_id=student_id,
            course_id=course_id,
            group=group,
        )
        return cast(str, group)

    async def get_feature_flags(self, study_group: str | None) -> dict[str, bool]:
        """Get feature flags based on study group.

        | Group            | Memory | Verification | Self-Improvement |
        |------------------|--------|-------------|-----------------|
        | control          | No     | No          | No              |
        | treatment_memory | Yes    | No          | No              |
        | treatment_full   | Yes    | Yes         | Yes             |
        """
        if not study_group:
            # No study active - enable everything
            return {
                "memory_enabled": True,
                "verification_enabled": True,
                "self_improvement_enabled": True,
            }

        return {
            "memory_enabled": study_group in ("treatment_memory", "treatment_full"),
            "verification_enabled": study_group == "treatment_full",
            "self_improvement_enabled": study_group == "treatment_full",
        }

    async def log_event(
        self,
        study_id: str,
        event_type: str,
        event_data: dict[str, Any],
        student_id: str | None = None,
    ) -> None:
        """Log a research event for later analysis."""
        self.db.add(
            ResearchEvent(
                study_id=study_id,
                student_id=student_id,
                event_type=event_type,
                event_data=event_data,
            )
        )
        await self.db.flush()
