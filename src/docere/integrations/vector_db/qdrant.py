"""Qdrant vector database client."""

from qdrant_client import AsyncQdrantClient, models
import structlog

from docere.config import settings

logger = structlog.get_logger()


class QdrantStore:
    """Qdrant vector database for semantic memory storage and retrieval."""

    def __init__(self) -> None:
        self.client = AsyncQdrantClient(url=settings.qdrant_url)
        self.dimensions = settings.embedding_dimensions

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
        """Upsert a vector with payload."""
        await self.client.upsert(
            collection_name=collection_name,
            points=[
                models.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=payload,
                )
            ],
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
        """Search for similar vectors with optional filtering."""
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
