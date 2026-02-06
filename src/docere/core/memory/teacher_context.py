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

            # Compress via Q&A distillation for large materials
            if len(content) > 3000:
                compressed = await self._compress_material(
                    content=content,
                    title=material.get("title", ""),
                    material_type=material.get("type", "document"),
                )
                content = compressed

            chunks = self._chunk_text(content, max_chars=2000)
            for i, chunk in enumerate(chunks):
                embedding = await generate_embedding(chunk)
                await self.qdrant.upsert(
                    collection_name=collection,
                    point_id=str(uuid.uuid4()),
                    vector=embedding,
                    payload={
                        "course_id": course_id,
                        "material_type": material.get("type", "document"),
                        "title": material.get("title", ""),
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

    async def refresh_course(self, course_id: str) -> None:
        """Sync any new/updated materials from LMS."""
        # TODO: Diff against stored materials, update changed ones
        pass

    async def retrieve_relevant_context(
        self,
        course_id: str,
        query: str,
        max_chunks: int = 3,
    ) -> str:
        """Retrieve course materials relevant to a student's query."""
        collection = f"{COLLECTION_PREFIX}_{course_id}"
        query_embedding = await generate_embedding(query)

        results = await self.qdrant.search(
            collection_name=collection,
            query_vector=query_embedding,
            top_k=max_chunks,
            score_threshold=0.55,
        )

        if not results:
            return ""

        context_parts = []
        for r in results:
            payload = r.get("payload", {})
            title = payload.get("title", "")
            content = payload.get("content", "")
            context_parts.append(f"[{title}]\n{content}")

        return "\n\n".join(context_parts)

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
