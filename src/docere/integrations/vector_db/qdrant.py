"""Qdrant vector database client with retry and circuit breaker."""

import httpx
import structlog
from qdrant_client import AsyncQdrantClient, models
from qdrant_client.http.exceptions import (
    ResponseHandlingException,
)

from docere.config import settings
from docere.core.resilience import CircuitBreaker, retry_async

logger = structlog.get_logger()

_qdrant_breaker = CircuitBreaker(service="qdrant", failure_threshold=5, recovery_timeout=30.0)

_RETRYABLE_QDRANT = (
    ResponseHandlingException,
    httpx.ConnectError,
    httpx.ReadTimeout,
    httpx.ConnectTimeout,
    ConnectionError,
    TimeoutError,
)


class QdrantStore:
    """Qdrant vector database for semantic memory storage and retrieval."""

    def __init__(self) -> None:
        self.client = AsyncQdrantClient(url=settings.qdrant_url, timeout=15.0)
        self.dimensions = settings.embedding_dimensions
        self.breaker = _qdrant_breaker

    async def ensure_collection(self, collection_name: str) -> None:
        """Create collection if it doesn't exist."""
        collections = await self.client.get_collections()
        existing = [c.name for c in collections.collections]
        if collection_name not in existing:
            await self.client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=self.dimensions,
                    distance=models.Distance.COSINE,
                ),
            )
            logger.info("Created Qdrant collection", collection=collection_name)

    async def upsert(
        self,
        collection_name: str,
        point_id: str,
        vector: list[float],
        payload: dict[str, object],
    ) -> None:
        """Upsert a vector with payload (retries on transient failures)."""
        await self.breaker.call(
            lambda: retry_async(
                lambda: self.client.upsert(
                    collection_name=collection_name,
                    points=[
                        models.PointStruct(
                            id=point_id,
                            vector=vector,
                            payload=payload,
                        )
                    ],
                ),
                max_retries=2,
                base_delay=0.3,
                retryable=_RETRYABLE_QDRANT,
            )
        )

    async def search(
        self,
        collection_name: str,
        query_vector: list[float],
        top_k: int = 5,
        score_threshold: float = 0.6,
        filter_conditions: dict[str, object] | None = None,
        with_vectors: bool = False,
    ) -> list[dict[str, object]]:
        """Search for similar vectors with optional filtering (retries on transient failures)."""
        query_filter = None
        if filter_conditions:
            must_conditions = [
                models.FieldCondition(
                    key=key,
                    match=models.MatchValue(value=value),
                )
                for key, value in filter_conditions.items()
            ]
            query_filter = models.Filter(must=must_conditions)

        async def _do_search():
            results = await self.client.query_points(
                collection_name=collection_name,
                query=query_vector,
                limit=top_k,
                score_threshold=score_threshold,
                query_filter=query_filter,
                with_vectors=with_vectors,
            )
            items = []
            for point in results.points:
                item: dict[str, object] = {
                    "id": str(point.id),
                    "score": point.score,
                    "payload": point.payload,
                }
                if with_vectors and point.vector:
                    item["vector"] = point.vector
                items.append(item)
            return items

        return await self.breaker.call(
            lambda: retry_async(
                _do_search,
                max_retries=2,
                base_delay=0.3,
                retryable=_RETRYABLE_QDRANT,
            )
        )

    async def scroll(
        self,
        collection_name: str,
        limit: int = 100,
        with_payload: bool = True,
        with_vectors: bool = False,
    ) -> list[dict[str, object]]:
        """Scroll through all points in a collection (no vector search)."""
        results, _ = await self.client.scroll(
            collection_name=collection_name,
            limit=limit,
            with_payload=with_payload,
            with_vectors=with_vectors,
        )
        return [
            {
                "id": str(point.id),
                "payload": point.payload or {},
            }
            for point in results
        ]

    async def delete_by_ids(
        self,
        collection_name: str,
        point_ids: list[str],
    ) -> None:
        """Delete specific points by their IDs."""
        if not point_ids:
            return
        await self.client.delete(
            collection_name=collection_name,
            points_selector=models.PointIdsList(points=point_ids),
        )

    async def delete(
        self,
        collection_name: str,
        filter_conditions: dict[str, object],
    ) -> None:
        """Delete vectors matching filter conditions."""
        must_conditions = [
            models.FieldCondition(
                key=key,
                match=models.MatchValue(value=value),
            )
            for key, value in filter_conditions.items()
        ]
        await self.client.delete(
            collection_name=collection_name,
            points_selector=models.FilterSelector(
                filter=models.Filter(must=must_conditions),
            ),
        )
