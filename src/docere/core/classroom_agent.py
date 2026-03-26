"""Multi-agent instructor system — fast heuristic routing + data-driven summaries + single LLM synthesis."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from docere.integrations.llm.client import ClaudeClient
from docere.integrations.vector_db.qdrant import QdrantStore
from docere.models.course import Enrollment
from docere.models.memory import ConceptMastery, StudentProfile
from docere.models.user import User

logger = structlog.get_logger()


# ── Human-readable helpers ──


def _confusion_label(score: float) -> str:
    if score < 0.2:
        return "very comfortable"
    if score < 0.35:
        return "mostly comfortable"
    if score < 0.5:
        return "somewhat confused"
    if score < 0.7:
        return "frequently confused"
    return "really struggling"


def _mastery_label(level: float) -> str:
    if level >= 0.85:
        return "strong grasp"
    if level >= 0.65:
        return "solid understanding"
    if level >= 0.45:
        return "partial understanding"
    if level >= 0.25:
        return "early stages"
    return "hasn't clicked yet"


def _grade_label(grade: float | None) -> str:
    if grade is None:
        return "no grade yet"
    if grade >= 90:
        return "A-range"
    if grade >= 80:
        return "B-range"
    if grade >= 70:
        return "C-range"
    if grade >= 60:
        return "D-range"
    return "below passing"


def _engagement_summary(counts: dict[str, int]) -> str:
    parts = []
    for level in ("high", "medium", "low", "inactive", "unknown"):
        n = counts.get(level, 0)
        if n == 0:
            continue
        if level == "high":
            parts.append(f"{n} are highly engaged")
        elif level == "medium":
            parts.append(f"{n} are moderately engaged")
        elif level == "low":
            parts.append(f"{n} have low engagement")
        elif level == "inactive":
            parts.append(f"{n} {'is' if n == 1 else 'are'} inactive")
        else:
            parts.append(f"{n} {'has' if n == 1 else 'have'} unknown engagement")
    return "; ".join(parts) if parts else f"{sum(counts.values())} students (no engagement data)"


# ── Data Types ──


class QueryIntent(StrEnum):
    CLASS_WIDE = "class_wide"
    STUDENT_SPECIFIC = "student_specific"
    MULTI_STUDENT = "multi_student"
    TOPIC_SPECIFIC = "topic_specific"
    META = "meta"


@dataclass
class RoutingDecision:
    intent: QueryIntent
    target_student_ids: list[str]
    target_student_names: list[str]
    topic_filter: str | None = None
    reasoning: str = ""


@dataclass
class StudentSummary:
    student_id: str
    student_name: str
    profile_summary: str
    relevant_memories: list[str]
    concept_mastery: dict[str, float]
    engagement_level: str
    avg_confusion: float
    current_grade: float | None
    topic_relevance: str
    key_findings: list[str]


@dataclass
class SourceRef:
    """A reference to a data source used to answer the query."""

    type: str  # "student_profile", "concept_mastery", "enrollment", "routing"
    label: str  # human-readable description
    student_name: str | None = None
    detail: str | None = None


@dataclass
class ClassroomContext:
    student_roster: list[dict]
    concept_overview: list[dict]
    total_students: int


@dataclass
class ClassroomResponse:
    text: str
    widgets: list[dict] = field(default_factory=list)
    sources: list[SourceRef] = field(default_factory=list)


# ── System Prompts ──

SYNTHESIS_SYSTEM_PROMPT = """You are an AI teaching assistant helping an instructor understand their class.
You will receive structured summaries from individual student analyses.
Synthesize them into a clear, actionable answer that any teacher can immediately understand.

Guidelines:
- Keep your ENTIRE response under 4-6 sentences. Be brief — teachers are busy.
- Mention student names but don't write a paragraph about each one. Group similar students together.
- End with one concrete suggestion the teacher can act on today.
- NEVER use markdown formatting. No **, no ### headers, no bullet lists. Write in plain conversational sentences.
- NEVER use raw numbers, decimals, or percentages. Say "struggling with recursion" not "confusion 0.72".
  Say "most of the class" not "74%". Use teacher-friendly language throughout.

Example of a good response:
"David and Tyler are both nearly checked out — minimal engagement and confused on the basics. Carlos is similar but shows flashes of understanding with conditionals. Raj is actually trying but hitting a wall on recursion and sorting. All four need help with foundational concepts. I'd suggest pulling them into a small group session focused on variables and data types before they fall further behind."

That's the right length and tone. No headers, no bold, no numbered lists."""


# ── ClassroomAgent ──


class ClassroomAgent:
    """Instructor query agent: heuristic routing, data-driven summaries, single LLM synthesis."""

    def __init__(self, db: AsyncSession, qdrant: QdrantStore, claude: ClaudeClient):
        self.db = db
        self.qdrant = qdrant
        self.claude = claude

    async def answer(
        self,
        course_id: str,
        question: str,
        history: list[dict[str, str]],
        source_filters: dict[str, bool] | None = None,
    ) -> ClassroomResponse:
        """Main entry point. Heuristic routing + 1 LLM call max."""
        # Source filters: which data types to include
        filters = source_filters or {}
        use_profiles = filters.get("profiles", True)
        use_mastery = filters.get("mastery", True)

        sources: list[SourceRef] = []

        # 1. Load aggregate context (2 SQL queries)
        context = await self._load_classroom_context(
            course_id,
            include_profiles=use_profiles,
            include_concepts=use_mastery,
        )

        if context.total_students == 0:
            return ClassroomResponse(text="No students are currently enrolled in this course.")

        sources.append(
            SourceRef(
                type="enrollment",
                label=f"Student roster ({context.total_students} enrolled)",
            )
        )

        # 2. Route with heuristics (no LLM)
        routing = self._route_heuristic(question, context)
        logger.info(
            "Routed instructor query",
            intent=routing.intent.value,
            target_count=len(routing.target_student_ids),
            topic_filter=routing.topic_filter,
            reasoning=routing.reasoning,
        )
        sources.append(
            SourceRef(
                type="routing",
                label=f"Query type: {routing.intent.value}",
                detail=routing.reasoning,
            )
        )

        # 3. META → answer from aggregate data (1 LLM call)
        if routing.intent == QueryIntent.META:
            if use_profiles:
                sources.append(
                    SourceRef(
                        type="student_profile", label="Aggregate engagement & confusion scores"
                    )
                )
            if use_mastery and context.concept_overview:
                sources.append(
                    SourceRef(
                        type="concept_mastery",
                        label=f"Top {len(context.concept_overview)} concepts by struggle count",
                    )
                )
            return await self._answer_meta(question, context, history, sources)

        # 4. For topic queries, refine targets to students who have that concept
        if routing.intent == QueryIntent.TOPIC_SPECIFIC and routing.topic_filter:
            topic_ids = await self._find_topic_students(course_id, routing.topic_filter)
            if topic_ids:
                roster_by_id = {s["id"]: s for s in context.student_roster}
                routing.target_student_ids = topic_ids
                routing.target_student_names = [
                    roster_by_id[sid]["name"] for sid in topic_ids if sid in roster_by_id
                ]
            if use_mastery:
                sources.append(
                    SourceRef(
                        type="concept_mastery",
                        label=f"Concept filter: {routing.topic_filter}",
                        detail=f"{len(routing.target_student_ids)} students matched",
                    )
                )

        # 5. Batch-load concept mastery for targets (1 SQL query)
        mastery: dict[str, dict[str, float]] = {}
        if use_mastery:
            mastery = await self._load_student_mastery(course_id, routing.target_student_ids)

        # 6. Build summaries from structured data (no LLM)
        summaries = self._build_summaries(routing, context, mastery)

        # Track per-student sources
        for s in summaries:
            roster_entry = next(
                (r for r in context.student_roster if r["id"] == s.student_id), None
            )
            profile = roster_entry["profile"] if roster_entry else None
            parts: list[str] = []
            if use_profiles and profile:
                parts.append("profile")
            if use_mastery and s.concept_mastery:
                parts.append(f"{len(s.concept_mastery)} concepts")
            sources.append(
                SourceRef(
                    type="student_profile",
                    label=", ".join(parts) if parts else "enrollment only",
                    student_name=s.student_name,
                )
            )

        # 7. Synthesize (1 LLM call)
        return await self._synthesize(question, routing, summaries, context, history, sources)

    # ── Heuristic Routing ──

    def _route_heuristic(self, question: str, context: ClassroomContext) -> RoutingDecision:
        """Route using pattern matching — instant, no LLM call."""
        q_lower = question.lower()

        # Match student names (word-boundary, skip short names to avoid false positives)
        matched = []
        for s in context.student_roster:
            parts = s["name"].lower().split()
            for part in parts:
                if len(part) < 3:
                    continue
                if re.search(r"\b" + re.escape(part) + r"\b", q_lower):
                    matched.append(s)
                    break

        # META: aggregate/count questions with no student mention
        meta_kw = ("how many", "how much", "total", "count", "average", "overall", "class size")
        if any(k in q_lower for k in meta_kw) and not matched:
            return RoutingDecision(
                intent=QueryIntent.META,
                target_student_ids=[],
                target_student_names=[],
                reasoning="Aggregate question",
            )

        # STUDENT_SPECIFIC
        if len(matched) == 1:
            return RoutingDecision(
                intent=QueryIntent.STUDENT_SPECIFIC,
                target_student_ids=[matched[0]["id"]],
                target_student_names=[matched[0]["name"]],
                reasoning=f"About {matched[0]['name']}",
            )

        # MULTI_STUDENT
        if len(matched) > 1:
            return RoutingDecision(
                intent=QueryIntent.MULTI_STUDENT,
                target_student_ids=[s["id"] for s in matched],
                target_student_names=[s["name"] for s in matched],
                reasoning=f"About {len(matched)} students",
            )

        # TOPIC_SPECIFIC: check against known concepts
        topic_filter = None
        for c in context.concept_overview:
            cname = c["concept_name"].lower()
            if len(cname) >= 3 and re.search(r"\b" + re.escape(cname) + r"\b", q_lower):
                topic_filter = c["concept_name"]
                break

        if topic_filter:
            # Will be refined in answer() with _find_topic_students
            return RoutingDecision(
                intent=QueryIntent.TOPIC_SPECIFIC,
                target_student_ids=[],
                target_student_names=[],
                topic_filter=topic_filter,
                reasoning=f"Topic: {topic_filter}",
            )

        # CLASS_WIDE: focus on most notable students
        notable = self._pick_notable_students(context, limit=6)
        return RoutingDecision(
            intent=QueryIntent.CLASS_WIDE,
            target_student_ids=[s["id"] for s in notable],
            target_student_names=[s["name"] for s in notable],
            reasoning="Class-wide, focusing on notable students",
        )

    @staticmethod
    def _pick_notable_students(context: ClassroomContext, limit: int = 6) -> list[dict]:
        """Pick the most notable students — struggling, disengaged, or outliers."""
        with_profiles = [s for s in context.student_roster if s["profile"]]
        if not with_profiles:
            return context.student_roster[:limit]

        def score(s: dict) -> float:
            p = s["profile"]
            # Higher score = more notable (needs attention)
            val = p.avg_confusion_score * 2
            if p.engagement_level in ("low", "inactive"):
                val += 1.5
            if p.current_grade is not None and p.current_grade < 70:
                val += 1.0
            return val

        with_profiles.sort(key=score, reverse=True)
        return with_profiles[:limit]

    # ── Data Loading ──

    async def _load_classroom_context(
        self,
        course_id: str,
        include_profiles: bool = True,
        include_concepts: bool = True,
    ) -> ClassroomContext:
        """Load aggregate data from PostgreSQL. No LLM calls."""
        if include_profiles:
            students_result = await self.db.execute(
                select(User.id, User.name, StudentProfile)
                .join(Enrollment, Enrollment.user_id == User.id)
                .outerjoin(
                    StudentProfile,
                    (StudentProfile.student_id == User.id)
                    & (StudentProfile.course_id == course_id),
                )
                .where(
                    Enrollment.course_id == course_id,
                    Enrollment.lms_role == "student",
                )
            )
            roster = [
                {"id": str(uid), "name": name, "profile": profile}
                for uid, name, profile in students_result.all()
            ]
        else:
            # Just enrollment, no profiles
            students_result = await self.db.execute(
                select(User.id, User.name)
                .join(Enrollment, Enrollment.user_id == User.id)
                .where(
                    Enrollment.course_id == course_id,
                    Enrollment.lms_role == "student",
                )
            )
            roster = [
                {"id": str(uid), "name": name, "profile": None}
                for uid, name in students_result.all()
            ]

        concept_overview: list[dict] = []
        if include_concepts:
            concepts_result = await self.db.execute(
                select(
                    ConceptMastery.concept_name,
                    func.avg(ConceptMastery.mastery_level).label("avg_mastery"),
                    func.sum(ConceptMastery.times_struggled).label("total_struggled"),
                    func.count(ConceptMastery.student_id.distinct()).label("student_count"),
                )
                .where(ConceptMastery.course_id == course_id)
                .group_by(ConceptMastery.concept_name)
                .order_by(func.sum(ConceptMastery.times_struggled).desc())
                .limit(30)
            )
            concept_overview = [
                {
                    "concept_name": r.concept_name,
                    "avg_mastery": float(r.avg_mastery),
                    "total_struggled": int(r.total_struggled),
                    "student_count": int(r.student_count),
                }
                for r in concepts_result.all()
            ]

        return ClassroomContext(
            student_roster=roster,
            concept_overview=concept_overview,
            total_students=len(roster),
        )

    async def _load_student_mastery(
        self,
        course_id: str,
        student_ids: list[str],
    ) -> dict[str, dict[str, float]]:
        """Batch-load concept mastery for target students — 1 SQL query."""
        if not student_ids:
            return {}

        result = await self.db.execute(
            select(ConceptMastery)
            .where(
                ConceptMastery.course_id == course_id,
                ConceptMastery.student_id.in_(student_ids),
            )
            .order_by(ConceptMastery.mastery_level.asc())
        )
        mastery: dict[str, dict[str, float]] = {}
        for r in result.scalars().all():
            sid = str(r.student_id)
            mastery.setdefault(sid, {})[r.concept_name] = r.mastery_level
        return mastery

    async def _find_topic_students(self, course_id: str, topic: str) -> list[str]:
        """Find students who have mastery data for a concept matching the topic."""
        result = await self.db.execute(
            select(ConceptMastery.student_id)
            .where(
                ConceptMastery.course_id == course_id,
                ConceptMastery.concept_name.ilike(f"%{topic}%"),
            )
            .distinct()
            .limit(10)
        )
        return [str(row[0]) for row in result.all()]

    # ── Summary Building (no LLM) ──

    def _build_summaries(
        self,
        routing: RoutingDecision,
        context: ClassroomContext,
        mastery_by_student: dict[str, dict[str, float]],
    ) -> list[StudentSummary]:
        """Build student summaries from structured data — no LLM calls."""
        roster_by_id = {s["id"]: s for s in context.student_roster}
        summaries = []

        for student_id in routing.target_student_ids:
            info = roster_by_id.get(student_id)
            if not info:
                continue

            profile: StudentProfile | None = info["profile"]
            mastery = mastery_by_student.get(student_id, {})

            # Profile summary
            if profile and profile.profile_summary:
                profile_summary = profile.profile_summary
            elif profile:
                profile_summary = (
                    f"{profile.total_interactions} interactions, "
                    f"{profile.engagement_level} engagement, "
                    f"{_confusion_label(profile.avg_confusion_score)}"
                )
            else:
                profile_summary = "No profile data"

            # Key findings from structured data
            findings: list[str] = []
            if profile:
                if profile.engagement_level in ("low", "inactive"):
                    findings.append(f"Has {profile.engagement_level} engagement")
                if profile.avg_confusion_score > 0.5:
                    findings.append(f"Is {_confusion_label(profile.avg_confusion_score)}")
                if profile.current_grade is not None and profile.current_grade < 70:
                    findings.append(f"Grade is {_grade_label(profile.current_grade)}")

            # Weak concepts
            weak = sorted(
                [(c, lvl) for c, lvl in mastery.items() if lvl < 0.45],
                key=lambda x: x[1],
            )
            if weak:
                findings.append(f"Struggling with {', '.join(c for c, _ in weak[:3])}")

            # Strong concepts
            strong = [c for c, lvl in mastery.items() if lvl >= 0.75]
            if strong:
                findings.append(f"Strong in {', '.join(strong[:3])}")

            if not findings:
                findings = ["No significant concerns"]

            summaries.append(
                StudentSummary(
                    student_id=student_id,
                    student_name=info["name"],
                    profile_summary=profile_summary,
                    relevant_memories=[],
                    concept_mastery=mastery,
                    engagement_level=profile.engagement_level if profile else "unknown",
                    avg_confusion=profile.avg_confusion_score if profile else 0.0,
                    current_grade=profile.current_grade if profile else None,
                    topic_relevance=profile_summary,
                    key_findings=findings,
                )
            )

        return summaries

    # ── Widget Building ──

    def _build_widget_data(
        self,
        routing: RoutingDecision,
        summaries: list[StudentSummary],
        context: ClassroomContext,
    ) -> list[dict]:
        """Pre-compute structured widget data from already-loaded context."""
        widgets: list[dict] = []
        roster_by_id = {s["id"]: s for s in context.student_roster}

        # Student Card: single-student queries
        if routing.intent == QueryIntent.STUDENT_SPECIFIC and len(summaries) == 1:
            s = summaries[0]
            roster_entry = roster_by_id.get(s.student_id, {})
            profile = roster_entry.get("profile")
            widgets.append(
                {
                    "type": "student_card",
                    "student_name": s.student_name,
                    "student_id": s.student_id,
                    "engagement_level": s.engagement_level,
                    "confusion_label": _confusion_label(s.avg_confusion),
                    "grade_label": _grade_label(s.current_grade),
                    "total_interactions": profile.total_interactions if profile else 0,
                    "top_concepts": [
                        {"name": c, "mastery_label": _mastery_label(lvl)}
                        for c, lvl in list(s.concept_mastery.items())[:6]
                    ],
                    "recent_activity": s.topic_relevance,
                    "profile_summary": s.profile_summary,
                }
            )

        # At-Risk Table: class-wide / multi-student
        at_risk = [
            s
            for s in summaries
            if s.avg_confusion > 0.5 or s.engagement_level in ("low", "inactive")
        ]
        if at_risk and routing.intent in (QueryIntent.CLASS_WIDE, QueryIntent.MULTI_STUDENT):
            widgets.append(
                {
                    "type": "at_risk_table",
                    "title": "At-Risk Students",
                    "students": [
                        {
                            "student_name": s.student_name,
                            "student_id": s.student_id,
                            "risk_reason": s.key_findings[0]
                            if s.key_findings
                            else "Low engagement",
                            "confusion_label": _confusion_label(s.avg_confusion),
                            "engagement_level": s.engagement_level,
                            "grade_label": _grade_label(s.current_grade),
                            "recommended_action": s.key_findings[-1]
                            if len(s.key_findings) > 1
                            else "Schedule check-in",
                        }
                        for s in at_risk[:10]
                    ],
                }
            )

        # Concept Heatmap: class-wide or topic-specific
        if context.concept_overview and routing.intent in (
            QueryIntent.CLASS_WIDE,
            QueryIntent.TOPIC_SPECIFIC,
        ):
            widgets.append(
                {
                    "type": "concept_heatmap",
                    "title": "Class Concept Mastery",
                    "cells": [
                        {
                            "concept": c["concept_name"],
                            "mastery_label": _mastery_label(c["avg_mastery"]),
                            "mastery_value": round(c["avg_mastery"], 2),
                            "student_count": c["student_count"],
                            "times_struggled": c["total_struggled"],
                        }
                        for c in context.concept_overview[:15]
                    ],
                }
            )

        # Engagement Chart: class-wide
        if routing.intent == QueryIntent.CLASS_WIDE:
            eng_buckets: dict[str, list[str]] = {}
            for s_data in context.student_roster:
                p = s_data["profile"]
                level = p.engagement_level if p else "unknown"
                eng_buckets.setdefault(level, []).append(s_data["name"])
            widgets.append(
                {
                    "type": "engagement_chart",
                    "title": "Class Engagement",
                    "total_students": context.total_students,
                    "buckets": [
                        {"level": level, "count": len(names), "student_names": names[:8]}
                        for level, names in eng_buckets.items()
                        if names
                    ],
                }
            )

        return widgets

    def _build_meta_widgets(self, context: ClassroomContext) -> list[dict]:
        """Build widgets for meta (aggregate) questions."""
        widgets: list[dict] = []

        if context.concept_overview:
            widgets.append(
                {
                    "type": "concept_heatmap",
                    "title": "Class Concept Mastery",
                    "cells": [
                        {
                            "concept": c["concept_name"],
                            "mastery_label": _mastery_label(c["avg_mastery"]),
                            "mastery_value": round(c["avg_mastery"], 2),
                            "student_count": c["student_count"],
                            "times_struggled": c["total_struggled"],
                        }
                        for c in context.concept_overview[:15]
                    ],
                }
            )

        eng_buckets: dict[str, list[str]] = {}
        for s_data in context.student_roster:
            p = s_data["profile"]
            level = p.engagement_level if p else "unknown"
            eng_buckets.setdefault(level, []).append(s_data["name"])
        if eng_buckets:
            widgets.append(
                {
                    "type": "engagement_chart",
                    "title": "Class Engagement",
                    "total_students": context.total_students,
                    "buckets": [
                        {"level": level, "count": len(names), "student_names": names[:8]}
                        for level, names in eng_buckets.items()
                        if names
                    ],
                }
            )

        return widgets

    # ── LLM Calls (only 1 per query) ──

    async def _answer_meta(
        self,
        question: str,
        context: ClassroomContext,
        history: list[dict[str, str]],
        sources: list[SourceRef] | None = None,
    ) -> ClassroomResponse:
        """Answer simple meta questions from aggregate data only."""
        with_profiles = [s for s in context.student_roster if s["profile"]]
        roster_summary = f"{context.total_students} students enrolled."
        if with_profiles:
            avg_confusion = sum(s["profile"].avg_confusion_score for s in with_profiles) / len(
                with_profiles
            )
            eng_counts: dict[str, int] = {}
            for s in with_profiles:
                lvl = s["profile"].engagement_level or "unknown"
                eng_counts[lvl] = eng_counts.get(lvl, 0) + 1
            roster_summary += (
                f" Overall, students are {_confusion_label(avg_confusion)}."
                f" Engagement: {_engagement_summary(eng_counts)}."
            )

        concept_lines = []
        for c in context.concept_overview[:10]:
            label = _mastery_label(c["avg_mastery"])
            struggled = c["total_struggled"]
            n_students = c["student_count"]
            concept_lines.append(
                f"- {c['concept_name']}: class has {label} "
                f"({n_students} students have worked on it, "
                f"{struggled} times someone struggled)"
            )

        system_prompt = (
            "You are an instructor's AI teaching assistant.\n"
            "Answer in 2-4 plain sentences. No markdown, no bold, no headers, no bullet lists.\n"
            "Use teacher-friendly language — NEVER output raw numbers or decimals.\n\n"
            f"Class: {roster_summary}\n\n"
            f"Top concepts by struggle:\n{chr(10).join(concept_lines) or 'No concept data yet.'}"
        )

        messages = [*history[-10:], {"role": "user", "content": question}]
        text = await self.claude.chat(
            system_prompt=system_prompt,
            messages=messages,
            max_tokens=300,
            temperature=0.4,
        )

        widgets = self._build_meta_widgets(context)
        return ClassroomResponse(text=text, widgets=widgets, sources=sources or [])

    async def _synthesize(
        self,
        question: str,
        routing: RoutingDecision,
        summaries: list[StudentSummary],
        context: ClassroomContext,
        history: list[dict[str, str]],
        sources: list[SourceRef] | None = None,
    ) -> ClassroomResponse:
        """Synthesize summaries into a final answer — the only LLM call for non-meta queries."""
        summary_blocks = []
        for s in summaries:
            mastery_str = ", ".join(
                f"{c} ({_mastery_label(lvl)})" for c, lvl in list(s.concept_mastery.items())[:5]
            )
            block = (
                f"### {s.student_name}\n"
                f"Profile: {s.profile_summary}\n"
                f"Engagement: {s.engagement_level} | "
                f"Comfort level: {_confusion_label(s.avg_confusion)} | "
                f"Grade: {_grade_label(s.current_grade)}\n"
                f"Key concepts: {mastery_str or 'none tracked'}\n"
                f"Findings:\n" + "\n".join(f"- {f}" for f in s.key_findings)
            )
            summary_blocks.append(block)

        aggregate_section = ""
        if routing.intent in (QueryIntent.CLASS_WIDE, QueryIntent.TOPIC_SPECIFIC):
            top_concepts = ", ".join(c["concept_name"] for c in context.concept_overview[:5])
            aggregate_section = (
                f"\n## Class Aggregate\n"
                f"Total students: {context.total_students}\n"
                f"Students analyzed in detail: {len(summaries)}\n"
                f"Top struggled concepts: {top_concepts or 'none'}"
            )

        topic_line = f"Topic filter: {routing.topic_filter}" if routing.topic_filter else ""
        system_prompt = (
            f"{SYNTHESIS_SYSTEM_PROMPT}\n\n"
            f"## Analysis Scope\n"
            f"Intent: {routing.intent.value}\n"
            f"{topic_line}\n"
            f"{aggregate_section}\n\n"
            f"## Individual Student Analyses\n"
            f"{chr(10).join(summary_blocks) if summary_blocks else 'No student data available.'}"
        )

        messages = [*history[-10:], {"role": "user", "content": question}]
        text = await self.claude.chat(
            system_prompt=system_prompt,
            messages=messages,
            max_tokens=400,
            temperature=0.4,
        )

        widgets = self._build_widget_data(routing, summaries, context)
        return ClassroomResponse(text=text, widgets=widgets, sources=sources or [])
