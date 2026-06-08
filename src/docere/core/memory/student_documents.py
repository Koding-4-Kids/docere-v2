"""Student document ingestion: parse, chunk, embed, and retrieve uploaded materials.

Mirrors TeacherContextManager but is student-scoped. No compression —
students upload specific reference materials they want searchable verbatim.
"""

import uuid
from typing import Any

import structlog

from docere.config import settings
from docere.integrations.llm.embeddings import generate_embedding, generate_embeddings_batch
from docere.integrations.vector_db.qdrant import QdrantStore

logger = structlog.get_logger()

ALLOWED_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".pptx",
    ".xlsx",
    ".html",
    ".htm",
    ".txt",
    ".md",
    ".png",
    ".jpg",
    ".jpeg",
}


def collection_name_for(student_id: str, course_id: str) -> str:
    """Qdrant collection name for a student's documents in a course."""
    return f"{settings.student_doc_collection_prefix}_{student_id}_{course_id}"


class StudentDocumentManager:
    """Parse, chunk, embed, and retrieve student-uploaded documents."""

    def __init__(self, qdrant: QdrantStore):
        self.qdrant = qdrant

    async def parse_document(self, file_path: str) -> tuple[str, int]:
        """Parse a document and return extracted text + page count.

        This is the first step: just extract text, no embedding.
        """
        text, page_count, _sections = await self._parse_document(file_path)
        if not text or len(text.strip()) < 50:
            raise ValueError("Document contains too little text to process")
        return text, page_count

    async def embed_document(
        self,
        doc_id: str,
        student_id: str,
        course_id: str,
        text: str,
    ) -> int:
        """Chunk and embed already-parsed text into Qdrant.

        This is the second step: called when user confirms "Add to Collection".
        Returns chunk_count.
        """
        collection = collection_name_for(student_id, course_id)
        await self.qdrant.ensure_collection(collection)

        # Build sections from the text (paragraph-based)
        sections = [{"title": "", "content": text, "page": None}]
        chunks = self._build_chunks(text, sections)

        # Batch embed
        all_vectors: list[list[float]] = []
        batch_size = 100
        for i in range(0, len(chunks), batch_size):
            batch_texts = [c["embed_text"] for c in chunks[i : i + batch_size]]
            vectors = await generate_embeddings_batch(batch_texts)
            all_vectors.extend(vectors)

        # Upsert all into Qdrant
        for chunk, vector in zip(chunks, all_vectors):
            await self.qdrant.upsert(
                collection_name=collection,
                point_id=str(uuid.uuid4()),
                vector=vector,
                payload={
                    "doc_id": doc_id,
                    "title": chunk.get("title", ""),
                    "section_title": chunk.get("section_title", ""),
                    "page_number": chunk.get("page_number"),
                    "chunk_index": chunk["chunk_index"],
                    "content": chunk["content"],
                },
            )

        logger.info(
            "Student document embedded",
            doc_id=doc_id,
            student_id=student_id,
            chunks=len(chunks),
        )
        return len(chunks)

    async def ingest_document(
        self,
        doc_id: str,
        file_path: str,
        student_id: str,
        course_id: str,
    ) -> tuple[int, int]:
        """Legacy: parse + embed in one step (used by ARQ worker)."""
        text, page_count = await self.parse_document(file_path)
        chunk_count = await self.embed_document(doc_id, student_id, course_id, text)
        return chunk_count, page_count

    async def delete_document(self, doc_id: str, student_id: str, course_id: str) -> None:
        """Remove all vectors for a document from Qdrant."""
        collection = collection_name_for(student_id, course_id)
        try:
            await self.qdrant.delete(
                collection_name=collection,
                filter_conditions={"doc_id": doc_id},
            )
        except Exception as e:
            logger.warning("Failed to delete document vectors", doc_id=doc_id, error=str(e))

    async def delete_collection(self, student_id: str, course_id: str) -> None:
        """Delete the entire Qdrant collection for a student/course (cleanup)."""
        collection = collection_name_for(student_id, course_id)
        try:
            await self.qdrant.client.delete_collection(collection)
        except Exception:
            pass

    async def retrieve_relevant(
        self,
        student_id: str,
        course_id: str,
        query: str,
        max_chunks: int = 3,
    ) -> str:
        """Search student's uploaded docs for content relevant to query.

        Returns formatted context string, or empty string if no docs.
        """
        collection = collection_name_for(student_id, course_id)

        try:
            query_embedding = await generate_embedding(query)
            results = await self.qdrant.search(
                collection_name=collection,
                query_vector=query_embedding,
                top_k=max_chunks,
                score_threshold=0.20,
            )
        except Exception:
            # Collection doesn't exist or search failed — student has no docs
            return ""

        if not results:
            return ""

        parts = []
        for r in results:
            payload = r.get("payload", {})
            title = payload.get("title", "")
            section = payload.get("section_title", "")
            page = payload.get("page_number")
            content = payload.get("content", "")

            header = title
            if section:
                header = f"{title} — {section}" if title else section
            if page:
                header += f" (p. {page})"

            parts.append(f"[{header}]\n{content}")

        return "\n\n".join(parts)

    # ── Parsing ──

    async def _parse_document(self, file_path: str) -> tuple[str, int, list[dict[str, Any]]]:
        """Parse a document using Docling. Falls back to pypdf for simple PDFs.

        Returns:
            (full_text, page_count, sections)
            sections: list of {"title": str, "content": str, "page": int|None}
        """
        try:
            return await self._parse_with_docling(file_path)
        except Exception as e:
            logger.warning("Docling parsing failed, trying pypdf fallback", error=str(e))

        # Fallback: pypdf for PDFs
        if file_path.lower().endswith(".pdf"):
            return await self._parse_with_pypdf(file_path)

        raise ValueError(f"Could not parse document: {file_path}")

    async def _parse_with_docling(self, file_path: str) -> tuple[str, int, list[dict[str, Any]]]:
        """Parse with Docling for rich structure extraction."""
        import asyncio

        def _sync_parse():
            from docling.document_converter import DocumentConverter

            converter = DocumentConverter()
            result = converter.convert(file_path)
            doc = result.document

            full_text = doc.export_to_markdown()
            page_count = getattr(doc, "num_pages", None) or 0

            # Extract sections from document structure
            sections = []
            for item in doc.iterate_items():
                if hasattr(item, "text") and item.text:
                    section = {
                        "title": getattr(item, "label", ""),
                        "content": item.text,
                        "page": getattr(item, "prov", [{}])[0].get("page_no")
                        if hasattr(item, "prov") and item.prov
                        else None,
                    }
                    sections.append(section)

            return full_text, page_count, sections

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _sync_parse)

    async def _parse_with_pypdf(self, file_path: str) -> tuple[str, int, list[dict[str, Any]]]:
        """Fallback: parse PDF with pypdf (already a dependency)."""
        import asyncio

        def _sync_parse():
            from pypdf import PdfReader

            reader = PdfReader(file_path)
            pages = []
            sections = []
            for i, page in enumerate(reader.pages):
                text = page.extract_text() or ""
                pages.append(text)
                if text.strip():
                    sections.append(
                        {
                            "title": f"Page {i + 1}",
                            "content": text,
                            "page": i + 1,
                        }
                    )

            return "\n".join(pages), len(reader.pages), sections

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _sync_parse)

    # ── Chunking ──

    def _build_chunks(
        self, full_text: str, sections: list[dict[str, Any]], max_chars: int = 2000
    ) -> list[dict[str, Any]]:
        """Build chunks from sections, falling back to paragraph splitting."""
        chunks: list[dict[str, Any]] = []
        chunk_index = 0

        if sections:
            for section in sections:
                content = section.get("content", "")
                if not content or len(content.strip()) < 30:
                    continue

                sub_chunks = self._chunk_text(content, max_chars)
                for sub in sub_chunks:
                    title = section.get("title", "")
                    embed_text = f"{title}\n\n{sub}" if title else sub
                    chunks.append(
                        {
                            "content": sub,
                            "embed_text": embed_text,
                            "section_title": title,
                            "page_number": section.get("page"),
                            "title": "",
                            "chunk_index": chunk_index,
                        }
                    )
                    chunk_index += 1
        else:
            # No sections — fall back to paragraph splitting
            sub_chunks = self._chunk_text(full_text, max_chars)
            for sub in sub_chunks:
                chunks.append(
                    {
                        "content": sub,
                        "embed_text": sub,
                        "section_title": "",
                        "page_number": None,
                        "title": "",
                        "chunk_index": chunk_index,
                    }
                )
                chunk_index += 1

        return chunks

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
