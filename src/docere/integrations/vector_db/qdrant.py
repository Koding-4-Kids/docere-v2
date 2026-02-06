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
        )
        return [
            {
                "id": str(point.id),
                "score": point.score,
                "payload": point.payload,
            }
            for point in results.points
        ]

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
