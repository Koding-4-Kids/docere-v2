"""Memory compression: CARTRIDGES-inspired context distillation.

Compresses clusters of raw memories into summary records to keep
context windows manageable while preserving key information.
"""
# E501 intentional here: file holds long prompt/instruction string constants.
# ruff: noqa: E501

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from docere.integrations.llm.client import ClaudeClient
from docere.integrations.vector_db.qdrant import QdrantStore
from docere.models.memory import MemoryRecord

logger = structlog.get_logger()

COMPRESS_MEMORIES_PROMPT = """You are summarizing a student's learning interactions for an AI tutoring system.
Given the following {count} memory records for a student, generate a concise summary that preserves:
1. Key concepts the student struggled with
2. Learning patterns (what works, what doesn't)
3. Important breakthroughs or persistent confusions
4. Overall trajectory (improving, stagnating, declining)

Memory records:
{memories}

Write a 3-5 sentence summary that captures the essential learning state.
Focus on actionable insights a tutor would need."""


class MemoryCompressor:
    """Compresses raw memories into efficient summaries."""

    def __init__(self, db: AsyncSession, claude: ClaudeClient, qdrant: QdrantStore):
        self.db = db
        self.claude = claude
        self.qdrant = qdrant

    async def compress_student_memories(
        self,
        student_id: str,
        course_id: str,
        threshold: int = 50,
    ) -> int:
        """Compress memories for a student if they exceed threshold.

        Groups similar memories by type, generates summaries via Claude,
        marks originals as compressed.

        Returns number of memories compressed.
        """
        # Count uncompressed memories
        count_result = await self.db.execute(
            select(func.count(MemoryRecord.id)).where(
                MemoryRecord.student_id == student_id,
                MemoryRecord.course_id == course_id,
                MemoryRecord.is_compressed.is_(False),
            )
        )
        total = count_result.scalar_one()

        if total < threshold:
            return 0

        # Fetch all uncompressed memories grouped by type
        result = await self.db.execute(
            select(MemoryRecord)
            .where(
                MemoryRecord.student_id == student_id,
                MemoryRecord.course_id == course_id,
                MemoryRecord.is_compressed.is_(False),
            )
            .order_by(MemoryRecord.created_at.asc())
        )
        memories = result.scalars().all()

        # Group by memory type
        groups: dict[str, list[MemoryRecord]] = {}
        for mem in memories:
            groups.setdefault(mem.memory_type, []).append(mem)

        compressed_count = 0

        for memory_type, group in groups.items():
            if len(group) < 10:
                continue

            # Process in batches of 20
            for i in range(0, len(group), 20):
                batch = group[i : i + 20]
                summary = await self._compress_batch(batch, memory_type)

                # Create the summary record
                summary_record = MemoryRecord(
                    student_id=student_id,
                    course_id=course_id,
                    memory_type=f"compressed_{memory_type}",
                    content=summary,
                    source="compression",
                    metadata_={
                        "compressed_from": [str(m.id) for m in batch],
                        "original_count": len(batch),
                        "date_range": {
                            "start": batch[0].created_at.isoformat(),
                            "end": batch[-1].created_at.isoformat(),
                        },
                    },
                )
                self.db.add(summary_record)
                await self.db.flush()

                # Collect embedding IDs for Qdrant cleanup
                stale_ids = [mem.embedding_id for mem in batch if mem.embedding_id]

                # Mark originals as compressed
                for mem in batch:
                    mem.is_compressed = True
                    mem.compressed_into = summary_record.id

                # Remove stale vectors from Qdrant
                if stale_ids:
                    try:
                        collection = f"interactions_{course_id}"
                        await self.qdrant.delete_by_ids(collection, stale_ids)
                    except Exception:
                        logger.warning(
                            "Failed to clean stale Qdrant vectors",
                            count=len(stale_ids),
                        )

                compressed_count += len(batch)

        await self.db.flush()

        logger.info(
            "Memories compressed",
            student_id=student_id,
            course_id=course_id,
            compressed=compressed_count,
            remaining=total - compressed_count,
        )
        return compressed_count

    async def _compress_batch(self, memories: list[MemoryRecord], memory_type: str) -> str:
        """Compress a batch of memories into a summary via Claude."""
        memory_text = "\n".join(
            f"[{m.created_at.strftime('%Y-%m-%d')}] ({m.memory_type}) {m.content[:200]}"
            for m in memories
        )

        prompt = COMPRESS_MEMORIES_PROMPT.format(
            count=len(memories),
            memories=memory_text,
        )

        summary = await self.claude.chat(
            system_prompt="You are a student learning interaction summarizer.",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.3,
        )
        return summary

    async def compress_all(self, threshold: int = 50) -> int:
        """Compress memories across all courses/students. Called by weekly background task."""
        # Find all (student, course) pairs with enough uncompressed memories
        result = await self.db.execute(
            select(MemoryRecord.student_id, MemoryRecord.course_id)
            .where(MemoryRecord.is_compressed.is_(False))
            .group_by(MemoryRecord.student_id, MemoryRecord.course_id)
            .having(func.count(MemoryRecord.id) >= threshold)
        )
        pairs = result.all()

        total_compressed = 0
        for student_id, course_id in pairs:
            compressed = await self.compress_student_memories(
                str(student_id), str(course_id), threshold
            )
            total_compressed += compressed

        logger.info(
            "Global compression complete", pairs=len(pairs), total_compressed=total_compressed
        )
        return total_compressed

    async def compress_all_students(self, course_id: str, threshold: int = 50) -> dict[str, int]:
        """Run compression for all students in a course. Called by weekly background task."""
        result = await self.db.execute(
            select(MemoryRecord.student_id)
            .where(
                MemoryRecord.course_id == course_id,
                MemoryRecord.is_compressed.is_(False),
            )
            .group_by(MemoryRecord.student_id)
            .having(func.count(MemoryRecord.id) >= threshold)
        )
        student_ids = [row[0] for row in result.all()]

        results = {}
        for sid in student_ids:
            compressed = await self.compress_student_memories(str(sid), course_id, threshold)
            results[str(sid)] = compressed

        logger.info(
            "Course compression complete",
            course_id=course_id,
            students_compressed=len(results),
        )
        return results
