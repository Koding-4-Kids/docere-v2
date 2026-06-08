"""Memory layer: assembles complete memory context for student interactions.

Combines:
- Teacher context: auto-pulled syllabus, lectures, course materials from LMS
- Student profile: past struggles, strengths, learning preferences
- Interaction history: semantically relevant past conversations
- LMS data: recent grades, upcoming deadlines, submission status
"""

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from docere.core.memory.concept_utils import normalize_concept
from docere.core.memory.interaction_store import InteractionStore
from docere.core.memory.student_profile import StudentProfileBuilder
from docere.core.memory.teacher_context import TeacherContextManager
from docere.integrations.llm.client import ClaudeClient
from docere.integrations.llm.embeddings import generate_embedding
from docere.integrations.vector_db.qdrant import QdrantStore
from docere.models.conversation import Conversation, Message
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

CONVERSATION_SUMMARY_PROMPT = """Summarize this tutoring conversation for an instructor's reference.

Conversation ({message_count} messages, {duration}):
{transcript}

Respond with ONLY a JSON object:
{{"summary": "2-4 sentence narrative of the conversation arc", "key_struggles": ["concept1"], "breakthroughs": ["concept2"], "overall_confusion": 0.5, "sentiment_arc": "confused -> guided -> understood"}}

Focus on: what the student struggled with, any breakthroughs, and the learning trajectory.
Keep the summary concise and data-driven."""

# How long a conversation must be idle before it gets summarized
CONVERSATION_IDLE_THRESHOLD = timedelta(hours=1)


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
                pct = (
                    f"{g['score']}/{g['max_score']}"
                    if g.get("max_score")
                    else str(g.get("score", "N/A"))
                )
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
        assignment_id: str | None = None,
        max_tokens: int = 8000,
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
            self.teacher_ctx.retrieve_relevant_context(
                course_id,
                current_query,
                max_chunks=3,
                assignment_id=assignment_id,
            ),
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
                memory_strings.append(f"Student: {student_msg[:200]}\nTutor: {agent_resp[:300]}")

        # Token budgeting: materials > profile > grades > history
        # Materials get the highest priority because the agent needs to
        # see actual assignment content to help students effectively.
        budget = max_tokens
        context = MemoryContext(
            teacher_context="",
            student_profile="",
        )

        # 1. Teacher context (course materials — highest priority)
        if teacher_context:
            tokens = _estimate_tokens(teacher_context)
            if tokens <= budget:
                context.teacher_context = teacher_context
                budget -= tokens
            else:
                # Reserve at least half the budget for materials
                char_limit = max(budget, max_tokens // 2) * 4
                context.teacher_context = teacher_context[:char_limit]
                budget = max(0, budget - _estimate_tokens(context.teacher_context))

        # 2. Profile (~200 tokens)
        if profile_str:
            tokens = _estimate_tokens(profile_str)
            if tokens <= budget:
                context.student_profile = profile_str
                budget -= tokens

        # 3. Concept mastery
        context.concept_mastery = mastery_dict
        if mastery_dict:
            mastery_text = "\n".join(f"- {c}: {l:.0%}" for c, l in mastery_dict.items())
            budget -= _estimate_tokens(mastery_text)

        # 4. Recent grades
        context.recent_grades = recent_grades
        if recent_grades:
            grades_text = "\n".join(
                f"- {g.get('title', '')}: {g.get('score', '')}/{g.get('max_score', '')}"
                for g in recent_grades[:5]
            )
            budget -= _estimate_tokens(grades_text)
        budget = max(0, budget)

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
            concepts = [normalize_concept(c) for c in data.get("concepts", []) if c.strip()][:4]
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

    async def update_live_metrics(
        self,
        student_id: str,
        course_id: str,
        concepts: list[str],
        confusion_score: float,
        sentiment: str,
    ) -> None:
        """Update StudentProfile + ConceptMastery per-message without storing a memory.

        This replaces the per-message capture_interaction() call. Concepts and
        mastery stay live-updated, but no Qdrant vector or MemoryRecord is created.
        The actual memory is deferred to conversation-level summarization.
        """
        await self.profile_builder.update_from_interaction(
            student_id=student_id,
            course_id=course_id,
            concepts=concepts,
            confusion_score=confusion_score,
            sentiment=sentiment,
        )
        await self.db.flush()

    async def summarize_stale_conversations(
        self,
        student_id: str,
        course_id: str,
    ) -> int:
        """Find and summarize conversations that have been idle for 1+ hour.

        Called at the start of handle_message() so stale conversations get
        summarized before the new message is processed.

        Returns the number of conversations summarized.
        """
        cutoff = datetime.now(timezone.utc) - CONVERSATION_IDLE_THRESHOLD

        result = await self.db.execute(
            select(Conversation.id, Conversation.student_id, Conversation.course_id).where(
                Conversation.student_id == student_id,
                Conversation.course_id == course_id,
                Conversation.status == "active",
                Conversation.summarized.is_(False),
                Conversation.last_message_at < cutoff,
            )
        )
        stale = result.all()

        if not stale:
            return 0

        count = 0
        for conv_id, s_id, c_id in stale:
            try:
                await self.summarize_conversation(
                    conversation_id=str(conv_id),
                    student_id=str(s_id),
                    course_id=str(c_id),
                )
                count += 1
            except Exception as e:
                logger.warning(
                    "Failed to summarize stale conversation",
                    conversation_id=str(conv_id),
                    error=str(e),
                )

        logger.info("Summarized stale conversations", count=count, student_id=student_id)
        return count

    async def summarize_conversation(
        self,
        conversation_id: str,
        student_id: str,
        course_id: str,
    ) -> None:
        """Generate a single summary memory for an entire conversation.

        1. Fetch all messages
        2. Claude summarizes the arc
        3. Store 1 Qdrant vector + 1 MemoryRecord
        4. Mark conversation as summarized
        """
        # Fetch messages
        result = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
        )
        messages = result.scalars().all()

        if len(messages) < 2:
            # Too short to summarize — just mark it
            conv_result = await self.db.execute(
                select(Conversation).where(Conversation.id == conversation_id)
            )
            conv = conv_result.scalar_one_or_none()
            if conv:
                conv.summarized = True
                await self.db.flush()
            return

        # Build transcript
        transcript_lines = []
        for msg in messages:
            role = "Student" if msg.role == "user" else "Tutor"
            transcript_lines.append(f"{role}: {msg.content[:300]}")
        transcript = "\n".join(transcript_lines)

        # Cap transcript to avoid huge prompts
        if len(transcript) > 4000:
            transcript = transcript[:4000] + "\n[...truncated]"

        # Calculate duration
        first_msg = messages[0].created_at
        last_msg = messages[-1].created_at
        duration_mins = int((last_msg - first_msg).total_seconds() / 60)
        duration_str = f"{duration_mins} minutes" if duration_mins > 0 else "< 1 minute"

        # Call Claude for summary
        prompt = CONVERSATION_SUMMARY_PROMPT.format(
            message_count=len(messages),
            duration=duration_str,
            transcript=transcript,
        )

        try:
            raw = await self.claude.chat(
                system_prompt="You are an educational conversation summarizer. Respond with only JSON.",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300,
                temperature=0.3,
            )
            data = json.loads(raw.strip())
            summary_text = data.get("summary", "")
            key_struggles = data.get("key_struggles", [])
            breakthroughs = data.get("breakthroughs", [])
            overall_confusion = max(0.0, min(1.0, float(data.get("overall_confusion", 0.5))))
            sentiment_arc = data.get("sentiment_arc", "")
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning("Conversation summary parse failed, using fallback", error=str(e))
            summary_text = f"Conversation with {len(messages)} messages over {duration_str}."
            key_struggles = []
            breakthroughs = []
            overall_confusion = 0.5
            sentiment_arc = ""

        # Collect all concepts from the conversation (normalized for matching)
        all_concepts = list(
            set(normalize_concept(c) for c in key_struggles + breakthroughs if c.strip())
        )

        # Build the full summary content for storage
        full_summary = summary_text
        if sentiment_arc:
            full_summary += f" Arc: {sentiment_arc}."

        # Generate embedding and store in Qdrant
        embedding = await generate_embedding(full_summary)
        point_id = await self.interaction_store.store(
            student_id=student_id,
            course_id=course_id,
            student_message=full_summary,  # summary goes in the searchable field
            agent_response="",
            embedding=embedding,
            metadata={
                "concepts": all_concepts,
                "confusion_score": overall_confusion,
                "sentiment": sentiment_arc,
                "memory_type": "conversation_summary",
                "conversation_id": conversation_id,
                "message_count": len(messages),
            },
        )

        # Store MemoryRecord in PostgreSQL
        memory = MemoryRecord(
            student_id=student_id,
            course_id=course_id,
            memory_type="conversation_summary",
            content=full_summary[:2000],
            embedding_id=point_id,
            concepts=all_concepts,
            sentiment=sentiment_arc or None,
            confusion_score=overall_confusion,
            source="chat",
            metadata_={
                "conversation_id": conversation_id,
                "message_count": len(messages),
                "duration_minutes": duration_mins,
                "key_struggles": key_struggles,
                "breakthroughs": breakthroughs,
            },
        )
        self.db.add(memory)

        # Mark conversation as summarized
        conv_result = await self.db.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        conv = conv_result.scalar_one_or_none()
        if conv:
            conv.summarized = True

        await self.db.flush()

        logger.info(
            "Conversation summarized",
            conversation_id=conversation_id,
            message_count=len(messages),
            concepts=all_concepts,
            confusion=overall_confusion,
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
