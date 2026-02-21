"""Teacher context management: auto-pulled from LMS.

Handles ingestion and compression of course materials:
- Syllabus, assignments, rubrics (auto-pulled from Canvas/Moodle)
- Lecture files and attachments
- Module structure
- CARTRIDGES-inspired compression via synthetic Q&A distillation
"""

import uuid

import structlog

from docere.integrations.llm.client import ClaudeClient
from docere.integrations.llm.embeddings import generate_embedding
from docere.integrations.vector_db.qdrant import QdrantStore

logger = structlog.get_logger()

COLLECTION_PREFIX = "materials"

COMPRESS_PROMPT = """You are compressing course material for an AI tutoring system.
Given the following course material, generate 5-10 synthetic Q&A pairs that capture
the most important concepts, requirements, and information a tutor would need to
help students with this material.

Material type: {material_type}
Title: {title}

Content:
{content}

Generate Q&A pairs in this format:
Q: [Question a student might ask]
A: [Concise answer based on the material]

Focus on key concepts, requirements, deadlines, and common points of confusion."""


class TeacherContextManager:
    """Manages teacher/course context auto-pulled from LMS."""

    def __init__(self, qdrant: QdrantStore, claude: ClaudeClient):
        self.qdrant = qdrant
        self.claude = claude

    async def ingest_course(
        self,
        course_id: str,
        syllabus: str | None,
        materials: list[dict[str, str]],
    ) -> int:
        """Ingest all course materials. Called on first LTI launch.

        Teacher does nothing - everything is auto-pulled from LMS.

        Args:
            course_id: Internal course UUID
            syllabus: Raw syllabus HTML/text (auto-pulled from LMS)
            materials: List of {"title": ..., "content": ..., "type": ...}

        Returns:
            Number of chunks embedded
        """
        collection = f"{COLLECTION_PREFIX}_{course_id}"
        await self.qdrant.ensure_collection(collection)

        chunks_embedded = 0

        # Embed syllabus
        if syllabus:
            chunks = self._chunk_text(syllabus, max_chars=2000)
            for i, chunk in enumerate(chunks):
                embedding = await generate_embedding(chunk)
                await self.qdrant.upsert(
                    collection_name=collection,
                    point_id=str(uuid.uuid4()),
                    vector=embedding,
                    payload={
                        "course_id": course_id,
                        "material_type": "syllabus",
                        "title": f"Syllabus (part {i + 1})",
                        "content": chunk,
                    },
                )
                chunks_embedded += 1

        # Embed each material
        for material in materials:
            content = material.get("content", "")
            if not content or len(content.strip()) < 50:
                continue

            # For assignments/exams, always store raw content so the agent
            # can reference actual questions.  Only compress generic materials
            # (e.g. lecture notes, pages) that are very large.
            mat_type = material.get("type", "document")
            if mat_type not in ("assign", "quiz") and len(content) > 6000:
                compressed = await self._compress_material(
                    content=content,
                    title=material.get("title", ""),
                    material_type=mat_type,
                )
                content = compressed

            title = material.get("title", "")
            chunks = self._chunk_text(content, max_chars=2000)
            for i, chunk in enumerate(chunks):
                # Prepend title so the embedding captures which material this is
                embed_text = f"{title}\n\n{chunk}" if title else chunk
                embedding = await generate_embedding(embed_text)
                await self.qdrant.upsert(
                    collection_name=collection,
                    point_id=str(uuid.uuid4()),
                    vector=embedding,
                    payload={
                        "course_id": course_id,
                        "material_type": mat_type,
                        "title": title,
                        "content": chunk,
                    },
                )
                chunks_embedded += 1

        logger.info(
            "Course materials ingested",
            course_id=course_id,
            chunks=chunks_embedded,
        )
        return chunks_embedded

    async def refresh_course(
        self,
        course_id: str,
        updated_materials: list[dict[str, str]],
    ) -> int:
        """Re-embed materials that have changed.

        Deletes old Qdrant vectors for the given materials, then re-embeds them.

        Args:
            course_id: Internal course UUID
            updated_materials: List of {"title": ..., "content": ..., "type": ...}

        Returns:
            Number of chunks re-embedded
        """
        collection = f"{COLLECTION_PREFIX}_{course_id}"
        chunks_embedded = 0

        for material in updated_materials:
            title = material.get("title", "")
            content = material.get("content", "")
            if not content or len(content.strip()) < 50:
                continue

            # Delete old vectors for this material
            await self.qdrant.delete(
                collection_name=collection,
                filter_conditions={"title": title},
            )

            # Only compress non-assignment materials that are very large
            mat_type = material.get("type", "document")
            if mat_type not in ("assign", "quiz") and len(content) > 6000:
                content = await self._compress_material(
                    content=content,
                    title=title,
                    material_type=mat_type,
                )

            # Re-embed
            chunks = self._chunk_text(content, max_chars=2000)
            for i, chunk in enumerate(chunks):
                embed_text = f"{title}\n\n{chunk}" if title else chunk
                embedding = await generate_embedding(embed_text)
                await self.qdrant.upsert(
                    collection_name=collection,
                    point_id=str(uuid.uuid4()),
                    vector=embedding,
                    payload={
                        "course_id": course_id,
                        "material_type": material.get("type", "document"),
                        "title": title,
                        "content": chunk,
                    },
                )
                chunks_embedded += 1

        logger.info(
            "Course materials refreshed",
            course_id=course_id,
            materials=len(updated_materials),
            chunks=chunks_embedded,
        )
        return chunks_embedded

    async def retrieve_relevant_context(
        self,
        course_id: str,
        query: str,
        max_chunks: int = 3,
        assignment_id: str | None = None,
    ) -> str:
        """Retrieve course materials relevant to a student's query.

        Always includes a material index (titles of everything in the course)
        so the agent knows what's available, plus detailed content for the
        top matching chunks.

        When assignment_id is provided, prioritizes assignment-type materials
        so the student's current assignment content appears first.
        """
        collection = f"{COLLECTION_PREFIX}_{course_id}"

        # Build a material index from all points in the collection
        material_index = await self._get_material_index(collection)

        # Semantic search for detailed content
        query_embedding = await generate_embedding(query)

        assignment_results: list[dict[str, object]] = []
        general_results: list[dict[str, object]] = []

        try:
            # When an assignment is active, do a targeted search for assignment
            # materials first so they appear at the top of context
            if assignment_id:
                assignment_results = await self.qdrant.search(
                    collection_name=collection,
                    query_vector=query_embedding,
                    top_k=2,
                    score_threshold=0.15,
                    filter_conditions={"material_type": "assign"},
                )

            general_results = await self.qdrant.search(
                collection_name=collection,
                query_vector=query_embedding,
                top_k=max_chunks + 2,
                score_threshold=0.15,
            )
        except Exception as e:
            logger.warning(
                "Teacher context search failed",
                collection=collection,
                error=str(e),
            )

        # Merge: assignment-specific results first, then general (deduplicated by point ID)
        seen_ids: set[str] = set()
        merged: list[dict[str, object]] = []
        for r in assignment_results + general_results:
            point_id = r.get("id", "")
            if point_id in seen_ids:
                continue
            seen_ids.add(point_id)
            merged.append(r)

        context_parts = []

        # Always include the material index so the agent knows what exists
        if material_index:
            context_parts.append(f"[Available Course Materials]\n{material_index}")

        # Add detailed content — allow one extra slot when assignment is active
        limit = max_chunks + 1 if assignment_id and assignment_results else max_chunks
        for r in merged[:limit]:
            payload = r.get("payload", {})
            title = payload.get("title", "")
            content = payload.get("content", "")
            context_parts.append(f"[{title}]\n{content}")

        return "\n\n".join(context_parts)

    async def _get_material_index(self, collection: str) -> str:
        """Build a lightweight index of all materials in a collection.

        Returns a bulleted list like:
          - Assignment: Assignment 1: Variables and Data Types
          - Assignment: Assignment 2: Loops and Conditionals
          - Page: Week 1: Introduction to Python
        """
        try:
            all_points = await self.qdrant.scroll(
                collection_name=collection,
                limit=100,
                with_payload=True,
                with_vectors=False,
            )
        except Exception:
            return ""

        # Deduplicate by title (multiple chunks share the same title)
        seen_titles: dict[str, str] = {}  # title -> material_type
        for point in all_points:
            payload = point.get("payload", {})
            title = payload.get("title", "")
            mat_type = payload.get("material_type", "")
            if title and title not in seen_titles:
                seen_titles[title] = mat_type

        if not seen_titles:
            return ""

        type_labels = {
            "assign": "Assignment",
            "quiz": "Quiz",
            "page": "Page",
            "resource": "Resource",
            "forum": "Forum",
            "syllabus": "Syllabus",
        }
        lines = []
        for title, mat_type in seen_titles.items():
            label = type_labels.get(mat_type, mat_type.title() if mat_type else "Material")
            lines.append(f"- {label}: {title}")

        return "\n".join(lines)

    async def _compress_material(
        self, content: str, title: str, material_type: str
    ) -> str:
        """Compress material via CARTRIDGES-inspired synthetic Q&A distillation."""
        prompt = COMPRESS_PROMPT.format(
            material_type=material_type,
            title=title,
            content=content[:8000],  # Limit to avoid token overflow
        )
        compressed = await self.claude.chat(
            system_prompt="You are a course material compression assistant.",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2000,
            temperature=0.3,
        )
        return compressed

    def _chunk_text(self, text: str, max_chars: int = 2000) -> list[str]:
        """Split text into chunks, preferring paragraph boundaries."""
        if len(text) <= max_chars:
            return [text]

        chunks = []
        paragraphs = text.split("\n\n")
        current_chunk = ""

        for paragraph in paragraphs:
            if len(current_chunk) + len(paragraph) + 2 > max_chars:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = paragraph
            else:
                current_chunk += "\n\n" + paragraph if current_chunk else paragraph

        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        return chunks
