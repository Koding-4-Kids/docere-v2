"""Interaction history store: semantic storage and retrieval of past conversations."""

import math
import uuid

import structlog

from docere.integrations.vector_db.qdrant import QdrantStore

logger = structlog.get_logger()

COLLECTION_PREFIX = "interactions"


def _collection_name(course_id: str) -> str:
    return f"{COLLECTION_PREFIX}_{course_id}"


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class InteractionStore:
    """Manages semantic storage and retrieval of tutoring interactions."""

    def __init__(self, qdrant: QdrantStore):
        self.qdrant = qdrant

    async def store(
        self,
        student_id: str,
        course_id: str,
        student_message: str,
        agent_response: str,
        embedding: list[float],
        metadata: dict[str, object] | None = None,
    ) -> str:
        """Store an interaction in Qdrant."""
        collection = _collection_name(course_id)
        await self.qdrant.ensure_collection(collection)

        point_id = str(uuid.uuid4())
        payload = {
            "student_id": student_id,
            "course_id": course_id,
            "student_message": student_message,
            "agent_response": agent_response,
            **(metadata or {}),
        }

        await self.qdrant.upsert(collection, point_id, embedding, payload)
        logger.info("Stored interaction", point_id=point_id, course_id=course_id)
        return point_id

    async def retrieve_relevant(
        self,
        student_id: str,
        course_id: str,
        query_embedding: list[float],
        top_k: int = 5,
        diversity_threshold: float = 0.65,
    ) -> list[dict[str, object]]:
        """Retrieve semantically relevant past interactions with diversity filtering.

        Uses a greedy diversity algorithm: iteratively add the most relevant
        result that is sufficiently different from already-selected results.
        This prevents returning near-duplicate memories.
        """
        collection = _collection_name(course_id)

        # Fetch more than needed so we can filter for diversity
        try:
            raw_results = await self.qdrant.search(
                collection_name=collection,
                query_vector=query_embedding,
                top_k=top_k * 3,
                score_threshold=0.55,
                filter_conditions={"student_id": student_id},
                with_vectors=True,
            )
        except Exception:
            # Collection may not exist yet (no interactions stored for this course)
            logger.debug("Interaction collection not found, returning empty", collection=collection)
            return []

        if not raw_results:
            return []

        # Greedy diversity filtering
        selected: list[dict[str, object]] = []
        selected_embeddings: list[list[float]] = []

        for result in raw_results:
            if len(selected) >= top_k:
                break

            result_vector = result.get("vector", query_embedding)

            # For the first result, always include it
            if not selected_embeddings:
                selected.append(result)
                selected_embeddings.append(result_vector)
                continue

            # Check similarity against all already-selected results
            is_diverse = True
            for prev_embedding in selected_embeddings:
                similarity = _cosine_similarity(result_vector, prev_embedding)
                if similarity > diversity_threshold:
                    is_diverse = False
                    break

            if is_diverse:
                selected.append(result)
                selected_embeddings.append(result_vector)

        return selected
