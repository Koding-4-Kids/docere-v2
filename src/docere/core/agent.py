"""Main tutoring agent orchestrator.

For each student message:
1. Retrieve memory context + profile + history (parallel)
2. Select an intervention strategy (UCB1 bandit)
3. Build a system prompt incorporating all context
4. Call LLM → return response immediately
5. Fire-and-forget: score previous interaction, extract concepts, summarize stale
"""
# E501 intentional here: file holds long prompt/instruction string constants.
# ruff: noqa: E501

import asyncio
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from docere.config import settings
from docere.core.improvement.strategy_archive import StrategyArchive, StrategyContext
from docere.core.memory.memory_layer import MemoryContext, MemoryLayer
from docere.core.verification.process_verifier import ProcessVerifier
from docere.integrations.llm.client import ClaudeClient
from docere.integrations.vector_db.qdrant import QdrantStore
from docere.models.conversation import Conversation, Message
from docere.models.course import Assignment
from docere.models.memory import MemoryRecord

logger = structlog.get_logger()

BASE_SYSTEM_PROMPT = """You are Docere, an AI tutor built into the student's LMS. You have access to their courses, assignments, and materials.

Your job is to help them learn — not give answers.

Response style:
- Keep it SHORT. 2-4 sentences max for most replies. Students skim long messages.
- Write like a helpful upperclassman texting, not a textbook. Be warm but brief.
- Use plain language. Avoid headers, numbered lists, and bold unless genuinely needed.
- Ask ONE focused question to guide their thinking, not a wall of information.
- If you reference course material, paraphrase — don't dump the whole thing.
- Never say you "don't have access" to their course. You're connected to their LMS.

Bad example (too long):
"Let's break down the requirements. 1. **Entities**: You need three entities... 2. **Relationships**: An actor can appear in... ### Common Misconception..."

Good example (concise):
"For the ER diagram — you need three entities: movies, studios, and actors. The tricky part is usually the actor-movie relationship. How many movies can an actor be in, and how many actors can a movie have?"
"""

STUDY_MATERIALS_INSTRUCTIONS = """
## Study Materials Generation

When a student explicitly asks you to create study materials, generate them inside a fenced artifact block. Format your response as:

1. A brief chat message (1-2 sentences) telling the student what you created.
2. Then a fenced artifact block:

```artifact
{"type": "notes", "title": "Your Title", "content": "markdown content here"}
```

### Notes (type: "notes")
Notes go directly into the student's notes editor panel. The student can see and edit them in real time.
- Content is markdown: headers (#, ##), bullet points, **bold** for key terms.
- If the student already has notes open, MERGE your content with theirs. Add new sections, fill gaps, or correct mistakes — don't overwrite everything they wrote.
- If the student has no notes yet, create a clean starting point.
- When the student says "make notes", "take notes", "add to my notes", "update my notes", or similar — always use this type.

### Other artifact types
- "flashcards": content is a JSON array string: [{"front": "question", "back": "answer"}, ...]. Generate 8-15 cards.
- "study_guide": content is a comprehensive markdown string with sections, definitions, examples, and practice questions.
- "slides": content is a JSON array string: [{"title": "Slide Title", "bullets": ["point 1", "point 2"]}, ...]. Generate 6-12 slides.

Rules:
- ONLY generate artifacts when the student explicitly asks for study materials, notes, flashcards, guides, or slides.
- Ground content in course materials from context — use actual assignment details and concepts.
- For flashcards/slides, the content field must be a valid JSON array encoded as a string.
- Always include a chat message OUTSIDE the artifact block.
"""


WIDGET_INSTRUCTIONS = """
## Interactive Widgets

You can generate two types of interactive widgets that render inline in the chat.

### Practice Quiz
When a student asks you to quiz them, test their understanding, or asks for practice questions, generate a quiz widget:

```widget
{"type": "practice_quiz", "title": "Quiz: Topic", "concept": "main concept", "questions": [{"question": "What is...?", "choices": ["A", "B", "C", "D"], "correct_index": 2, "correct_answer": "C", "explanation": "Because..."}, {"question": "Explain...", "correct_answer": "The answer is...", "explanation": "This works because..."}]}
```

Rules for practice quiz:
- Generate 3-5 questions per quiz
- Mix multiple-choice (with 4 choices + correct_index) and short-answer (no choices, just correct_answer)
- Ground questions in course material and current assignment context
- Write clear explanations for each answer
- Keep a brief chat message OUTSIDE the widget block

### Step-by-Step Hints
When a student is stuck on a problem and needs guidance but should discover the answer themselves, generate progressive hints instead of giving the answer directly:

```widget
{"type": "step_hints", "title": "Hints: topic", "problem_context": "What the student is working on", "hints": [{"text": "Vague conceptual hint..."}, {"text": "More specific hint..."}, {"text": "Very specific hint..."}, {"text": "Essentially the answer..."}]}
```

Rules for hints:
- Generate 3-5 hints, going from vague/conceptual to specific/concrete
- The last hint should essentially give the answer
- Only use when the student is stuck on a specific problem, not for general questions
- Keep a brief chat message OUTSIDE the widget block
"""

MEETING_SCHEDULING_INSTRUCTIONS = """
## Meeting Scheduling

The student can schedule meetings with their instructor directly through Docere. When the student asks to meet their professor/instructor, OR when they're clearly struggling, you MUST include an action block at the end of your response.

IMPORTANT: Do NOT tell the student to email their professor or suggest they contact them separately. Docere handles scheduling directly. Just write a brief supportive message and include the action block.

Your response format MUST be:
1. A short chat message (1-2 sentences) acknowledging their request
2. The action block:

```action
{"type": "meeting_suggestion", "reason": "Brief explanation", "concepts": ["concept1", "concept2"]}
```

Example response when student asks to schedule:
"I'd be happy to help you set up a meeting! Based on our conversations, it looks like discussing loops and functions would be really helpful.

```action
{"type": "meeting_suggestion", "reason": "You've been working through some challenging loop concepts", "concepts": ["for loops", "nested loops"]}
```"

Rules:
- ALWAYS include the action block — this triggers the scheduling UI for the student
- NEVER suggest emailing or contacting the professor manually
- Keep the reason concise and empathetic
- List specific concepts from the student's history
"""

# Keywords that indicate a student wants to schedule a meeting
MEETING_KEYWORDS = re.compile(
    r"\b(schedule a meeting|meet with my (professor|instructor|teacher|ta)|"
    r"office hours|book a meeting|set up a meeting|talk to my (professor|instructor|teacher))\b",
    re.IGNORECASE,
)


@dataclass
class AgentResponse:
    """Response from the tutoring agent."""

    content: str
    model_used: str
    token_count: int
    strategy_used: str | None
    memory_context_size: int
    artifact: dict | None = None
    action: dict | None = None
    widgets: list[dict] | None = None


class TutoringAgent:
    """Central agent that coordinates memory, strategy, and LLM calls."""

    def __init__(
        self,
        db: AsyncSession,
        qdrant: QdrantStore,
        claude: ClaudeClient,
    ):
        self.db = db
        self.claude = claude
        self.memory = MemoryLayer(db, qdrant, claude)
        self.strategies = StrategyArchive(db)
        self.verifier = ProcessVerifier(db, claude)

    async def handle_message(
        self,
        conversation_id: str,
        student_message: str,
        student_id: str,
        course_id: str,
        assignment_id: str | None = None,
        study_group: str | None = None,
    ) -> AgentResponse:
        """Process a student message and generate a tutoring response.

        Args:
            conversation_id: Active conversation ID
            student_message: The student's message
            student_id: Student user ID
            course_id: Course context ID
            assignment_id: Optional assignment the conversation is about
            study_group: Research study group (controls feature gating)

        Returns:
            AgentResponse with the AI tutoring response
        """
        # ── Fast path: get everything we need for the LLM call in parallel ──

        # These are all independent reads — run them concurrently
        async def _load_assignment() -> Assignment | None:
            if not assignment_id:
                return None
            r = await self.db.execute(select(Assignment).where(Assignment.id == assignment_id))
            return r.scalar_one_or_none()

        async def _load_memory() -> MemoryContext:
            if study_group == "control":
                return MemoryContext.empty()
            try:
                return await self.memory.retrieve_context(
                    student_id=student_id,
                    course_id=course_id,
                    current_query=student_message,
                    assignment_id=assignment_id,
                    max_tokens=settings.memory_max_context_tokens,
                )
            except RuntimeError as e:
                logger.warning("Memory retrieval failed, using empty context", error=str(e))
                return MemoryContext.empty()

        async def _load_profile():
            if study_group == "control":
                return None
            return await self.memory.profile_builder.get_profile(student_id, course_id)

        assignment, memory_ctx, profile, conversation_messages = await asyncio.gather(
            _load_assignment(),
            _load_memory(),
            _load_profile(),
            self._get_conversation_history(conversation_id),
        )

        # Build strategy context from profile
        strategy_ctx = None
        if profile:
            strategy_ctx = StrategyContext.from_profile(
                avg_confusion=profile.avg_confusion_score,
                total_interactions=profile.total_interactions,
                avg_interaction_score=profile.avg_interaction_score or 0.5,
            )

        # Select strategy + build prompt (fast, DB-only)
        strategy = await self.strategies.select_strategy(study_group, context=strategy_ctx)
        strategy_name = strategy.name if strategy else None

        # Determine if we should suggest meeting scheduling
        suggest_meeting = self._should_suggest_meeting(profile, student_message)

        system_prompt = self._build_system_prompt(
            memory_ctx,
            strategy,
            assignment,
            profile=profile,
            suggest_meeting=suggest_meeting,
        )

        # ── THE LLM call — this is what the user is waiting for ──
        conversation_messages.append({"role": "user", "content": student_message})
        response_text = await self.claude.chat(
            system_prompt=system_prompt,
            messages=conversation_messages,
            max_tokens=2048,
            temperature=0.7,
        )

        # ── Extract artifact, action, and widgets if present ──
        chat_text, artifact_data = self._extract_artifact(response_text)
        chat_text, action_data = self._extract_action(chat_text)
        chat_text, widget_list = self._extract_widgets(chat_text)

        # Force-inject meeting action if student explicitly asked but LLM missed the format
        explicit_meeting_request = bool(MEETING_KEYWORDS.search(student_message))
        if explicit_meeting_request and not action_data:
            struggle_concepts = []
            if profile and hasattr(profile, "top_confused_concepts"):
                struggle_concepts = profile.top_confused_concepts or []
            elif profile:
                # Fall back to extracting from memory context
                struggle_concepts = (
                    [c for c in (memory_ctx.concepts or [])]
                    if hasattr(memory_ctx, "concepts")
                    else []
                )

            action_data = {
                "type": "meeting_suggestion",
                "reason": "You'd like to meet with your instructor — let's get that scheduled.",
                "concepts": struggle_concepts[:5],
            }
            logger.info("Force-injected meeting action for explicit request")

        # ── Persist messages + return immediately ──
        now = datetime.now(UTC)

        student_msg = Message(
            conversation_id=conversation_id,
            role="user",
            content=student_message,
            created_at=now,
        )
        self.db.add(student_msg)

        assistant_msg = Message(
            conversation_id=conversation_id,
            role="assistant",
            content=chat_text,
            model_used=self.claude.default_model,
            token_count=len(response_text) // 4,
            metadata_={
                "strategy_id": str(strategy.id) if strategy else None,
                "strategy_name": strategy_name,
                "memory_tokens": memory_ctx.total_tokens,
                "strategy_context_key": strategy_ctx.key if strategy_ctx else None,
                "artifact": artifact_data,
                "action": action_data,
                "widgets": widget_list if widget_list else None,
            },
            created_at=now,
        )
        self.db.add(assistant_msg)

        # Update conversation timestamp
        result = await self.db.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        conversation = result.scalar_one_or_none()
        if conversation:
            conversation.last_message_at = now
            if strategy:
                conversation.strategy_id = strategy.id

        await self.db.commit()

        logger.info(
            "Agent response generated",
            conversation_id=conversation_id,
            strategy=strategy_name,
            memory_tokens=memory_ctx.total_tokens,
        )

        # ── Fire-and-forget: all non-critical work runs AFTER response ──
        # These don't block the user — they run in the background.
        asyncio.create_task(
            self._post_process(
                conversation_id=conversation_id,
                student_id=student_id,
                course_id=course_id,
                student_message=student_message,
                response_text=response_text,
                study_group=study_group,
                artifact_data=artifact_data,
                assistant_msg_id=str(assistant_msg.id),
            )
        )

        return AgentResponse(
            content=chat_text,
            model_used=self.claude.default_model,
            token_count=len(response_text) // 4,
            strategy_used=strategy_name,
            memory_context_size=memory_ctx.total_tokens,
            artifact=artifact_data,
            action=action_data,
            widgets=widget_list if widget_list else None,
        )

    async def _post_process(
        self,
        conversation_id: str,
        student_id: str,
        course_id: str,
        student_message: str,
        response_text: str,
        study_group: str | None,
        artifact_data: dict | None = None,
        assistant_msg_id: str | None = None,
    ) -> None:
        """Background post-processing: scoring, concept extraction, summarization.

        Runs as a fire-and-forget task so the student gets their response instantly.
        Uses its own DB session since the request session may be closed.
        """
        from docere.dependencies import async_session

        try:
            async with async_session() as db:
                bg_memory = MemoryLayer(db, self.memory.qdrant, self.claude)
                bg_verifier = ProcessVerifier(db, self.claude)
                bg_strategies = StrategyArchive(db)

                # 1. Score previous interaction
                if study_group != "control":
                    try:
                        await self._score_previous_interaction_bg(
                            db=db,
                            bg_verifier=bg_verifier,
                            bg_strategies=bg_strategies,
                            bg_memory=bg_memory,
                            conversation_id=conversation_id,
                            student_id=student_id,
                            course_id=course_id,
                            student_followup=student_message,
                        )
                    except Exception as e:
                        logger.warning("Background scoring failed", error=str(e))

                # 2. Extract concepts + update live metrics
                try:
                    concepts, confusion, sentiment = await bg_memory.extract_concepts(
                        student_message=student_message,
                        agent_response=response_text,
                    )
                    await bg_memory.update_live_metrics(
                        student_id=student_id,
                        course_id=course_id,
                        concepts=concepts,
                        confusion_score=confusion,
                        sentiment=sentiment,
                    )
                except Exception as e:
                    logger.warning("Background concept extraction failed", error=str(e))

                # 3. Persist flashcard artifacts to deck
                if artifact_data and artifact_data.get("type") == "flashcards":
                    try:
                        from docere.services.flashcard_service import FlashcardService

                        fc_svc = FlashcardService(db)
                        raw_content = artifact_data.get("content", "[]")
                        cards_json = (
                            json.loads(raw_content) if isinstance(raw_content, str) else raw_content
                        )
                        added = await fc_svc.add_cards_from_artifact(
                            student_id=student_id,
                            course_id=course_id,
                            cards_json=cards_json,
                            source_message_id=assistant_msg_id,
                            concepts=artifact_data.get("source_concepts", []),
                        )
                        if added:
                            logger.info("Flashcards persisted", count=added, course_id=course_id)
                    except Exception as e:
                        logger.warning("Failed to persist flashcard artifact", error=str(e))

                # 4. Summarize stale conversations
                if study_group != "control":
                    try:
                        await bg_memory.summarize_stale_conversations(
                            student_id=student_id,
                            course_id=course_id,
                        )
                    except Exception as e:
                        logger.warning("Background summarization failed", error=str(e))

                await db.commit()
        except Exception as e:
            logger.error("Background post-processing failed", error=str(e))

    async def _score_previous_interaction_bg(
        self,
        db: AsyncSession,
        bg_verifier: ProcessVerifier,
        bg_strategies: StrategyArchive,
        bg_memory: MemoryLayer,
        conversation_id: str,
        student_id: str,
        course_id: str,
        student_followup: str,
    ) -> None:
        """Score the previous assistant message (runs in background task)."""
        result = await db.execute(
            select(Message)
            .where(
                Message.conversation_id == conversation_id,
                Message.role == "assistant",
            )
            .order_by(Message.created_at.desc())
            .limit(1)
        )
        prev_assistant = result.scalar_one_or_none()
        if not prev_assistant:
            return

        result = await db.execute(
            select(Message)
            .where(
                Message.conversation_id == conversation_id,
                Message.role == "user",
                Message.created_at <= prev_assistant.created_at,
            )
            .order_by(Message.created_at.desc())
            .limit(1)
        )
        prev_student = result.scalar_one_or_none()
        if not prev_student:
            return

        now = datetime.now(UTC)
        time_delta = int((now - prev_assistant.created_at).total_seconds())

        verification = await bg_verifier.score_interaction(
            message_id=str(prev_assistant.id),
            conversation_id=conversation_id,
            student_id=student_id,
            student_message=prev_student.content,
            assistant_message=prev_assistant.content,
            student_followup=student_followup,
            time_to_followup=time_delta,
        )

        # Close the scoring loop: update StudentProfile.avg_interaction_score
        profile = await bg_memory.profile_builder.get_profile(student_id, course_id)
        if profile:
            n = profile.total_interactions or 1
            old_avg = profile.avg_interaction_score or 0.0
            profile.avg_interaction_score = (old_avg * (n - 1) + verification.composite_score) / n

        # If a strategy was used, record the outcome for the bandit
        metadata = prev_assistant.metadata_ or {}
        strategy_id = metadata.get("strategy_id")
        if strategy_id:
            mem_result = await db.execute(
                select(MemoryRecord.concepts)
                .where(MemoryRecord.source_message_id == prev_assistant.id)
                .limit(1)
            )
            concepts = mem_result.scalar_one_or_none() or []

            context_key = metadata.get("strategy_context_key")
            strategy_ctx = None
            if context_key:
                parts = context_key.split(":")
                if len(parts) == 3:
                    strategy_ctx = StrategyContext(*parts)

            await bg_strategies.record_outcome(
                strategy_id=strategy_id,
                conversation_id=conversation_id,
                score=verification.composite_score,
                interaction_score_id=verification.score_id,
                context_metadata={
                    "concepts": concepts,
                    "concept": concepts[0] if concepts else None,
                    "student_id": student_id,
                    "followup_type": verification.student_followup_type,
                    "helpfulness": verification.helpfulness_score,
                    "clarity": verification.clarity_score,
                    "engagement": verification.engagement_score,
                    "understanding_delta": verification.understanding_delta,
                },
                context=strategy_ctx,
            )

        logger.info(
            "Previous interaction scored (background)",
            message_id=str(prev_assistant.id),
            composite=f"{verification.composite_score:.2f}",
        )

    def _build_system_prompt(
        self,
        memory_ctx: MemoryContext,
        strategy: object | None,
        assignment: Assignment | None = None,
        profile: object | None = None,
        suggest_meeting: bool = False,
    ) -> str:
        """Build the full system prompt from memory context, strategy, and profile."""
        parts = [BASE_SYSTEM_PROMPT]

        # Add current assignment context (highest priority — before everything else)
        if assignment:
            assignment_section = f"\n## Current Assignment\nTitle: {assignment.title}"
            if assignment.due_at:
                assignment_section += f"\nDue: {assignment.due_at.strftime('%Y-%m-%d %H:%M')}"
            if assignment.description:
                assignment_section += f"\nDescription: {assignment.description}"
            if assignment.points_possible is not None:
                assignment_section += f"\nPoints: {assignment.points_possible}"
            assignment_section += (
                "\n\nThe student is asking about this specific assignment. "
                "You have the full assignment details above — do NOT ask them "
                "to paste or reiterate the assignment."
            )
            parts.append(assignment_section)

        # Add strategy instructions
        if strategy and hasattr(strategy, "prompt_template") and strategy.prompt_template:
            parts.append(f"\n## Teaching Strategy\n{strategy.prompt_template}")

        # Add memory context
        context_str = memory_ctx.to_system_context()
        if context_str:
            parts.append(f"\n## Student Context\n{context_str}")

        # Score-based prompt adaptation (reads from profile, no extra DB queries)
        if profile:
            adaptations = []
            if (profile.avg_interaction_score or 0) < 0.4 and profile.total_interactions >= 3:
                adaptations.append(
                    "Previous approaches haven't been effective with this student. "
                    "Try a completely different angle than what might have been tried before."
                )
            if profile.avg_confusion_score > 0.6 and profile.engagement_level != "high":
                adaptations.append(
                    "This student is frequently confused. Use very short, concrete "
                    "examples. Avoid abstract explanations."
                )
            if adaptations:
                parts.append("\n## Adaptation Notes\n" + "\n".join(adaptations))

        # Add study materials generation instructions
        parts.append(STUDY_MATERIALS_INSTRUCTIONS)

        # Add interactive widget instructions
        parts.append(WIDGET_INSTRUCTIONS)

        # Add meeting scheduling instructions when appropriate
        if suggest_meeting:
            parts.append(MEETING_SCHEDULING_INSTRUCTIONS)
            parts.append(
                "\n## Meeting Suggestion Active\n"
                "The student appears to be persistently struggling. "
                "Consider suggesting they schedule a meeting with their instructor."
            )

        # If no course materials were found, tell the agent explicitly
        if not memory_ctx.teacher_context:
            parts.append(
                "\n## Note\n"
                "No course materials have been uploaded for this course yet. "
                "You are still connected to the student's LMS — the instructor "
                "simply hasn't added materials. Help the student with what you "
                "know and do NOT claim you lack access to their course."
            )

        return "\n".join(parts)

    @staticmethod
    def _extract_artifact(response_text: str) -> tuple[str, dict | None]:
        """Extract a fenced ```artifact block from the LLM response.

        Returns:
            (clean_chat_text, artifact_dict | None)
            On parse failure, returns original text with None.
        """
        # Try strict pattern first, then progressively more lenient
        patterns = [
            r"```artifact\s*\n(.*?)\n\s*```",  # strict: newline-bounded
            r"```artifact\s*\n?([\s\S]*?)\n```",  # relaxed opening newline
            r"```artifact\s*\n?([\s\S]*?)```",  # no closing newline required
        ]
        match = None
        for pat in patterns:
            match = re.search(pat, response_text, re.DOTALL)
            if match:
                break
        if not match:
            logger.warning(
                "No artifact block found in response",
                has_artifact_keyword="```artifact" in response_text,
                response_len=len(response_text),
            )
            return response_text, None

        try:
            raw = match.group(1).strip()
            logger.debug("Extracted artifact raw content", raw_len=len(raw), raw_preview=raw[:200])
            artifact = json.loads(raw)

            # Validate required fields (title is optional)
            if not all(k in artifact for k in ("type", "content")):
                logger.warning("Artifact missing required fields", keys=list(artifact.keys()))
                return response_text, None
            if "title" not in artifact:
                artifact["title"] = artifact["type"].replace("_", " ").title()

            if artifact["type"] not in ("notes", "flashcards", "study_guide", "slides"):
                logger.warning("Unknown artifact type", type=artifact["type"])
                return response_text, None

            # Ensure content is always a string (LLM may return parsed JSON)
            if not isinstance(artifact["content"], str):
                artifact["content"] = json.dumps(artifact["content"])

            # Strip the artifact block from the chat text
            chat_text = response_text[: match.start()] + response_text[match.end() :]
            chat_text = chat_text.strip()

            return chat_text, artifact

        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("Failed to parse artifact block", error=str(e))
            return response_text, None

    @staticmethod
    def _extract_action(response_text: str) -> tuple[str, dict | None]:
        """Extract a fenced ```action block from the LLM response.

        Returns:
            (clean_chat_text, action_dict | None)
        """
        pattern = r"```action\s*\n(.*?)\n\s*```"
        match = re.search(pattern, response_text, re.DOTALL)
        if not match:
            return response_text, None

        try:
            raw = match.group(1).strip()
            action = json.loads(raw)

            if action.get("type") != "meeting_suggestion":
                return response_text, None

            if "reason" not in action:
                return response_text, None

            chat_text = response_text[: match.start()] + response_text[match.end() :]
            return chat_text.strip(), action

        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("Failed to parse action block", error=str(e))
            return response_text, None

    @staticmethod
    def _extract_widgets(response_text: str) -> tuple[str, list[dict]]:
        """Extract all ```widget blocks from the LLM response.

        Returns:
            (clean_chat_text, list_of_widget_dicts)
        """
        pattern = r"```widget\s*\n(.*?)\n\s*```"
        widgets: list[dict] = []
        clean = response_text

        for match in reversed(list(re.finditer(pattern, response_text, re.DOTALL))):
            try:
                raw = match.group(1).strip()
                widget = json.loads(raw)
                if "type" not in widget:
                    continue
                widgets.insert(0, widget)
                clean = clean[: match.start()] + clean[match.end() :]
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning("Failed to parse widget block", error=str(e))

        return clean.strip(), widgets

    @staticmethod
    def _should_suggest_meeting(profile: object | None, student_message: str) -> bool:
        """Determine if meeting scheduling instructions should be injected.

        Returns True when:
        1. Student explicitly asks about meeting/office hours, OR
        2. Student has persistently high confusion (>threshold for N+ sessions)
        """
        # Always inject if student explicitly asks
        if MEETING_KEYWORDS.search(student_message):
            return True

        # Proactive: inject when confusion is persistently high
        if profile and hasattr(profile, "avg_confusion_score"):
            if (
                profile.avg_confusion_score > settings.meeting_struggle_threshold
                and (profile.total_interactions or 0) >= settings.meeting_struggle_consecutive_count
            ):
                return True

        return False

    async def _get_conversation_history(
        self, conversation_id: str, max_messages: int = 20
    ) -> list[dict[str, str]]:
        """Fetch recent conversation history for Claude context."""
        result = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(max_messages)
        )
        messages = list(reversed(result.scalars().all()))

        return [{"role": msg.role, "content": msg.content} for msg in messages]
