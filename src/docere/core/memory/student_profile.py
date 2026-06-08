"""Student profile builder: tracks learning patterns and generates narrative summaries."""

from datetime import UTC, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from docere.core.memory.concept_utils import normalize_concept
from docere.integrations.llm.client import ClaudeClient
from docere.models.memory import ConceptMastery, MemoryRecord, StudentProfile

logger = structlog.get_logger()

NARRATIVE_PROMPT = """You are generating a concise student learning profile for an AI tutor.
Based on the following data about a student, write a 2-3 sentence narrative summary
that would help a tutor quickly understand this student's learning state.

Student stats:
- Total interactions: {total_interactions}
- Average confusion score: {avg_confusion:.2f}
- Engagement level: {engagement_level}
- Current grade: {current_grade}

Top struggles (concepts with lowest mastery):
{weak_concepts}

Recent memory highlights:
{recent_memories}

Write a concise profile summary. Example:
"Alex has been struggling with recursion for 2 weeks, asking 7 questions about it.
She responds well to visual analogies and step-by-step examples. Her quiz grades
on recursion topics are below class average but improving."
"""


class StudentProfileBuilder:
    """Builds and maintains student learning profiles."""

    def __init__(self, db: AsyncSession, claude: ClaudeClient):
        self.db = db
        self.claude = claude

    async def get_profile(self, student_id: str, course_id: str) -> StudentProfile | None:
        """Get the current student profile."""
        result = await self.db.execute(
            select(StudentProfile).where(
                StudentProfile.student_id == student_id,
                StudentProfile.course_id == course_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_or_create_profile(self, student_id: str, course_id: str) -> StudentProfile:
        """Get existing profile or create a new one."""
        profile = await self.get_profile(student_id, course_id)
        if not profile:
            profile = StudentProfile(
                student_id=student_id,
                course_id=course_id,
            )
            self.db.add(profile)
            await self.db.flush()
        return profile

    async def update_from_interaction(
        self,
        student_id: str,
        course_id: str,
        concepts: list[str],
        confusion_score: float,
        sentiment: str,
    ) -> None:
        """Update profile after an interaction."""
        profile = await self.get_or_create_profile(student_id, course_id)

        # Update aggregate stats
        profile.total_interactions += 1
        profile.total_messages += 1
        n = profile.total_interactions
        profile.avg_confusion_score = (profile.avg_confusion_score * (n - 1) + confusion_score) / n
        profile.last_interaction_at = datetime.now(UTC)

        # Update engagement level based on interaction frequency
        if n >= 20:
            profile.engagement_level = "high"
        elif n >= 10:
            profile.engagement_level = "medium"
        elif n >= 3:
            profile.engagement_level = "low"

        # Update concept mastery
        for concept in concepts:
            await self._update_concept(student_id, course_id, concept, confusion_score)

        await self.db.flush()

    async def _update_concept(
        self,
        student_id: str,
        course_id: str,
        concept_name: str,
        confusion_score: float,
    ) -> None:
        """Update mastery for a single concept using Bayesian Knowledge Tracing."""
        from docere.core.knowledge_tracing import BKTParams, bkt_update, confusion_to_correct

        concept_name = normalize_concept(concept_name)
        result = await self.db.execute(
            select(ConceptMastery).where(
                ConceptMastery.student_id == student_id,
                ConceptMastery.course_id == course_id,
                ConceptMastery.concept_name == concept_name,
            )
        )
        mastery = result.scalar_one_or_none()
        correct = confusion_to_correct(confusion_score)
        now = datetime.now(UTC)

        if mastery:
            mastery.times_practiced += 1
            if not correct:
                mastery.times_struggled += 1

            # Load or initialize BKT state from evidence JSONB
            evidence = mastery.evidence or {}
            p_learned = evidence.get("bkt_p_learned", mastery.mastery_level or 0.1)
            params = BKTParams(**evidence.get("bkt_params", {}))

            # BKT update
            p_learned = bkt_update(p_learned, correct, params)

            # Store back
            mastery.mastery_level = p_learned
            evidence["bkt_p_learned"] = p_learned
            evidence["bkt_params"] = {
                "p_l0": params.p_l0,
                "p_transit": params.p_transit,
                "p_guess": params.p_guess,
                "p_slip": params.p_slip,
            }

            # Keep last 20 observations for analysis
            obs_history = evidence.get("observation_history", [])
            obs_history.append(
                {
                    "correct": correct,
                    "confusion": confusion_score,
                    "timestamp": now.isoformat(),
                }
            )
            evidence["observation_history"] = obs_history[-20:]
            mastery.evidence = evidence
            mastery.last_practiced_at = now
        else:
            # First observation for this concept
            params = BKTParams()
            p_learned = bkt_update(params.p_l0, correct, params)

            self.db.add(
                ConceptMastery(
                    student_id=student_id,
                    course_id=course_id,
                    concept_name=concept_name,
                    mastery_level=p_learned,
                    times_practiced=1,
                    times_struggled=0 if correct else 1,
                    last_practiced_at=now,
                    evidence={
                        "bkt_p_learned": p_learned,
                        "bkt_params": {
                            "p_l0": params.p_l0,
                            "p_transit": params.p_transit,
                            "p_guess": params.p_guess,
                            "p_slip": params.p_slip,
                        },
                        "observation_history": [
                            {
                                "correct": correct,
                                "confusion": confusion_score,
                                "timestamp": now.isoformat(),
                            }
                        ],
                    },
                )
            )

    async def get_weak_concepts(
        self, student_id: str, course_id: str, threshold: float = 0.5
    ) -> list[dict[str, object]]:
        """Get concepts below mastery threshold."""
        result = await self.db.execute(
            select(ConceptMastery)
            .where(
                ConceptMastery.student_id == student_id,
                ConceptMastery.course_id == course_id,
                ConceptMastery.mastery_level < threshold,
            )
            .order_by(ConceptMastery.mastery_level.asc())
        )
        concepts = result.scalars().all()
        return [
            {
                "concept": c.concept_name,
                "mastery": c.mastery_level,
                "times_struggled": c.times_struggled,
            }
            for c in concepts
        ]

    async def generate_narrative_summary(self, student_id: str, course_id: str) -> str:
        """Generate a narrative profile summary via Claude."""
        profile = await self.get_or_create_profile(student_id, course_id)
        weak_concepts = await self.get_weak_concepts(student_id, course_id)

        # Get recent memories
        result = await self.db.execute(
            select(MemoryRecord)
            .where(
                MemoryRecord.student_id == student_id,
                MemoryRecord.course_id == course_id,
            )
            .order_by(MemoryRecord.created_at.desc())
            .limit(5)
        )
        recent_memories = result.scalars().all()

        weak_str = (
            "\n".join(
                f"- {c['concept']}: mastery {c['mastery']:.1%}, struggled {c['times_struggled']} times"
                for c in weak_concepts[:5]
            )
            or "No weak concepts identified yet."
        )

        memory_str = (
            "\n".join(f"- [{m.memory_type}] {m.content[:100]}" for m in recent_memories)
            or "No memories recorded yet."
        )

        prompt = NARRATIVE_PROMPT.format(
            total_interactions=profile.total_interactions,
            avg_confusion=profile.avg_confusion_score,
            engagement_level=profile.engagement_level,
            current_grade=f"{profile.current_grade:.1f}%" if profile.current_grade else "N/A",
            weak_concepts=weak_str,
            recent_memories=memory_str,
        )

        summary = await self.claude.chat(
            system_prompt="You are a student learning profiler.",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0.4,
        )

        profile.profile_summary = summary
        await self.db.flush()
        return summary
