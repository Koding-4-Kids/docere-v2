"""Memory layer: assembles complete memory context for student interactions.

Combines:
- Teacher context: auto-pulled syllabus, lectures, course materials from LMS
- Student profile: past struggles, strengths, learning preferences
- Interaction history: semantically relevant past conversations
- LMS data: recent grades, upcoming deadlines, submission status
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from docere.core.memory.interaction_store import InteractionStore
from docere.core.memory.student_profile import StudentProfileBuilder
from docere.core.memory.teacher_context import TeacherContextManager
from docere.integrations.llm.client import ClaudeClient
from docere.integrations.llm.embeddings import generate_embedding
from docere.integrations.vector_db.qdrant import QdrantStore
from docere.models.course import Assignment, Submission
from docere.models.memory import ConceptMastery, MemoryRecord

logger = structlog.get_logger()

EXTRACT_CONCEPTS_PROMPT = """Analyze this tutoring exchange and extract:

Student: {student_message}
Tutor: {agent_response}

Respond with ONLY a JSON object:
{{"concepts": ["concept1", "concept2"], "confusion_score": 0.0, "sentiment": "neutral"}}

Rules:
- concepts: 1-4 specific academic concepts discussed (e.g. "derivatives", "photosynthesis"). Use lowercase.
- confusion_score: 0.0 (student clearly understands) to 1.0 (student is very confused)
- sentiment: one of "positive", "neutral", "frustrated", "confused"
"""


@dataclass
class MemoryContext:
    """Complete memory context assembled for an interaction."""

    teacher_context: str
    student_profile: str
    relevant_memories: list[str] = field(default_factory=list)
    recent_grades: list[dict[str, object]] = field(default_factory=list)
    concept_mastery: dict[str, float] = field(default_factory=dict)
    total_tokens: int = 0

    @classmethod
    def empty(cls) -> "MemoryContext":
        """Create an empty context (for control group)."""
        return cls(teacher_context="", student_profile="")

    def to_system_context(self) -> str:
        """Format as a string block for the system prompt."""
        parts = []

        if self.student_profile:
            parts.append(f"## Student Profile\n{self.student_profile}")

        if self.concept_mastery:
            mastery_lines = [
                f"- {concept}: {level:.0%}" for concept, level in self.concept_mastery.items()
            ]
            parts.append("## Concept Mastery\n" + "\n".join(mastery_lines))

        if self.recent_grades:
            grade_lines = []
            for g in self.recent_grades[:5]:
                pct = f"{g['score']}/{g['max_score']}" if g.get("max_score") else str(g.get("score", "N/A"))
                grade_lines.append(f"- {g.get('title', 'Unknown')}: {pct}")
            parts.append("## Recent Grades\n" + "\n".join(grade_lines))

        if self.teacher_context:
            parts.append(f"## Course Materials\n{self.teacher_context}")

        if self.relevant_memories:
            parts.append("## Relevant Past Interactions\n" + "\n---\n".join(self.relevant_memories))

        return "\n\n".join(parts)


# Rough token estimation: 1 token ≈ 4 characters
def _estimate_tokens(text: str) -> int:
    return len(text) // 4


class MemoryLayer:
    """Unified memory retrieval and capture interface."""

    def __init__(
        self,
        db: AsyncSession,
        qdrant: QdrantStore,
        claude: ClaudeClient,
    ):
        self.db = db
        self.qdrant = qdrant
        self.claude = claude
        self.teacher_ctx = TeacherContextManager(qdrant, claude)
        self.interaction_store = InteractionStore(qdrant)
        self.profile_builder = StudentProfileBuilder(db, claude)

    async def retrieve_context(
        self,
        student_id: str,
        course_id: str,
        current_query: str,
        max_tokens: int = 4000,
    ) -> MemoryContext:
        """Assemble complete memory context for a student interaction.

        Parallel fetch:
        1. Qdrant: semantically relevant course materials
        2. Qdrant: relevant past interactions
        3. PostgreSQL: student profile + concept mastery + recent grades

        Token budget prioritizes: profile > struggles > materials > general history
        """
        query_embedding = await generate_embedding(current_query)

        # Fetch from all sources
        # Note: DB queries must be sequential (asyncpg doesn't allow concurrent
        # queries on the same connection). Qdrant calls can run in parallel.
        teacher_context, raw_interactions = await asyncio.gather(
            self.teacher_ctx.retrieve_relevant_context(course_id, current_query, max_chunks=3),
            self.interaction_store.retrieve_relevant(
                student_id, course_id, query_embedding, top_k=5
            ),
        )
        profile = await self.profile_builder.get_profile(student_id, course_id)
        weak_concepts = await self.profile_builder.get_weak_concepts(student_id, course_id)
        recent_grades = await self._get_recent_grades(student_id, course_id)

        # Build profile string
        profile_str = ""
        if profile and profile.profile_summary:
            profile_str = profile.profile_summary
        elif profile:
            profile_str = (
                f"Interactions: {profile.total_interactions}, "
                f"Engagement: {profile.engagement_level}, "
                f"Avg confusion: {profile.avg_confusion_score:.2f}"
            )

        # Build concept mastery dict
        mastery_dict: dict[str, float] = {}
        for c in weak_concepts:
            mastery_dict[c["concept"]] = c["mastery"]

        # Format interaction memories
        memory_strings = []
        for interaction in raw_interactions:
            payload = interaction.get("payload", {})
            student_msg = payload.get("student_message", "")
            agent_resp = payload.get("agent_response", "")
            if student_msg or agent_resp:
                memory_strings.append(
                    f"Student: {student_msg[:200]}\nTutor: {agent_resp[:300]}"
                )

        # Token budgeting: profile > struggles > materials > history
        budget = max_tokens
        context = MemoryContext(
            teacher_context="",
            student_profile="",
        )

        # 1. Profile (highest priority, ~200 tokens)
        if profile_str:
            tokens = _estimate_tokens(profile_str)
            if tokens <= budget:
                context.student_profile = profile_str
                budget -= tokens

        # 2. Concept mastery (~100 tokens)
        context.concept_mastery = mastery_dict

        # 3. Recent grades (~150 tokens)
        context.recent_grades = recent_grades

        # 4. Teacher context (course materials)
        if teacher_context:
            tokens = _estimate_tokens(teacher_context)
            if tokens <= budget:
                context.teacher_context = teacher_context
                budget -= tokens
            else:
                # Truncate to fit budget
                char_limit = budget * 4
                context.teacher_context = teacher_context[:char_limit]
                budget = 0

        # 5. Interaction history (lowest priority, fills remaining budget)
        if budget > 0:
            for mem in memory_strings:
                tokens = _estimate_tokens(mem)
                if tokens > budget:
                    break
                context.relevant_memories.append(mem)
                budget -= tokens

        context.total_tokens = max_tokens - budget

        logger.info(
            "Memory context assembled",
            student_id=student_id,
            course_id=course_id,
            tokens_used=context.total_tokens,
            memories=len(context.relevant_memories),
        )
        return context

    async def extract_concepts(
        self,
        student_message: str,
        agent_response: str,
    ) -> tuple[list[str], float, str]:
        """Extract concepts, confusion score, and sentiment from an exchange.

        Returns:
            (concepts, confusion_score, sentiment)
        """
        import json

        prompt = EXTRACT_CONCEPTS_PROMPT.format(
            student_message=student_message[:500],
            agent_response=agent_response[:500],
        )

        try:
            result = await self.claude.chat(
                system_prompt="You are an educational content analyzer. Respond with only JSON.",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=100,
                temperature=0.1,
            )
            data = json.loads(result.strip())
            concepts = [c.lower().strip() for c in data.get("concepts", []) if c.strip()][:4]
            confusion = max(0.0, min(1.0, float(data.get("confusion_score", 0.0))))
            sentiment = data.get("sentiment", "neutral")
            if sentiment not in ("positive", "neutral", "frustrated", "confused"):
                sentiment = "neutral"
            return concepts, confusion, sentiment
        except (json.JSONDecodeError, KeyError, ValueError):
            logger.warning("Concept extraction failed, using defaults")
            return [], 0.0, "neutral"

    async def capture_interaction(
        self,
        student_id: str,
        course_id: str,
        student_message: str,
        agent_response: str,
        concepts: list[str] | None = None,
        confusion_score: float = 0.0,
        sentiment: str | None = None,
    ) -> None:
        """Capture a tutoring interaction as a memory record.

        1. Generate embedding for Q+A pair
        2. Upsert into Qdrant
        3. Insert memory_record in PostgreSQL
        4. Update student profile + concept mastery
        """
        combined_text = f"Student: {student_message}\nTutor: {agent_response}"
        embedding = await generate_embedding(combined_text)

        # Store in Qdrant (vector DB)
        point_id = await self.interaction_store.store(
            student_id=student_id,
            course_id=course_id,
            student_message=student_message,
            agent_response=agent_response,
            embedding=embedding,
            metadata={
                "concepts": concepts or [],
                "confusion_score": confusion_score,
                "sentiment": sentiment or "neutral",
            },
        )

        # Store in PostgreSQL (relational)
        memory = MemoryRecord(
            student_id=student_id,
            course_id=course_id,
            memory_type="interaction",
            content=combined_text[:2000],
            embedding_id=point_id,
            concepts=concepts,
            sentiment=sentiment,
            confusion_score=confusion_score,
            source="chat",
        )
        self.db.add(memory)

        # Update student profile
        await self.profile_builder.update_from_interaction(
            student_id=student_id,
            course_id=course_id,
            concepts=concepts or [],
            confusion_score=confusion_score,
            sentiment=sentiment or "neutral",
        )

        await self.db.flush()

        logger.info(
            "Interaction captured",
            student_id=student_id,
            course_id=course_id,
            concepts=concepts,
        )

    async def integrate_grade(
        self,
        student_id: str,
        course_id: str,
        assignment_title: str,
        score: float,
        max_score: float,
        concepts: list[str] | None = None,
    ) -> None:
        """Integrate a grade from LMS into the memory layer.

        Creates a memory record and updates concept mastery based on performance.
        """
        percentage = (score / max_score * 100) if max_score > 0 else 0
        content = f"Scored {score}/{max_score} ({percentage:.0f}%) on '{assignment_title}'"

        # Infer confusion from grade: low grade = high confusion
        confusion = max(0.0, min(1.0, 1.0 - (percentage / 100)))

        memory = MemoryRecord(
            student_id=student_id,
            course_id=course_id,
            memory_type="grade",
            content=content,
            concepts=concepts,
            confusion_score=confusion,
            source="lms_sync",
            metadata_={"score": score, "max_score": max_score, "percentage": percentage},
        )
        self.db.add(memory)

        # Update concept mastery based on grade performance
        if concepts:
            for concept in concepts:
                await self.profile_builder._update_concept(
                    student_id=student_id,
                    course_id=course_id,
                    concept_name=concept,
                    confusion_score=confusion,
                )

        # Update overall grade on profile
        profile = await self.profile_builder.get_or_create_profile(student_id, course_id)
        profile.current_grade = percentage

        await self.db.flush()

        logger.info(
            "Grade integrated",
            student_id=student_id,
            assignment=assignment_title,
            score=f"{score}/{max_score}",
        )

    async def _get_recent_grades(
        self, student_id: str, course_id: str, limit: int = 5
    ) -> list[dict[str, object]]:
        """Fetch recent grades from PostgreSQL."""
        result = await self.db.execute(
            select(Submission, Assignment.title, Assignment.points_possible)
            .join(Assignment, Submission.assignment_id == Assignment.id)
            .where(
                Submission.student_id == student_id,
                Assignment.course_id == course_id,
                Submission.score.isnot(None),
            )
            .order_by(Submission.graded_at.desc())
            .limit(limit)
        )
        rows = result.all()
        return [
            {
                "title": title,
                "score": sub.score,
                "max_score": points,
                "graded_at": sub.graded_at.isoformat() if sub.graded_at else None,
            }
            for sub, title, points in rows
        ]
