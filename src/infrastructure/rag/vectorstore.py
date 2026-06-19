"""
Qdrant vector store implementation.

Implements VectorStoreInterface from the domain layer using the Qdrant
client library. Supports collection management, upsert, search, and delete.
"""

from typing import Any

import structlog
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from src.config.settings import Settings
from src.domain.interfaces.vector_store import VectorStoreInterface

logger = structlog.get_logger(__name__)


class QdrantVectorStore(VectorStoreInterface):
    """
    Qdrant vector store implementation.

    Wraps the Qdrant client to implement the domain VectorStoreInterface.
    Supports both self-hosted and cloud Qdrant instances.
    """

    def __init__(self, settings: Settings) -> None:
        self._client = QdrantClient(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
        )
        self._default_collection = settings.qdrant_collection
        logger.info(
            "qdrant.initialized",
            host=settings.qdrant_host,
            port=settings.qdrant_port,
        )

    def _resolve_collection(self, collection_name: str | None) -> str:
        """Resolve collection name, falling back to default."""
        return collection_name or self._default_collection

    async def create_collection(
        self,
        collection_name: str,
        vector_size: int = 1536,
        distance: str = "Cosine",
    ) -> bool:
        """
        Create a new Qdrant collection.

        Args:
            collection_name: Name for the new collection
            vector_size: Embedding dimension (default: 1536 for text-embedding-3-small)
            distance: Distance metric

        Returns:
            True if created, False if already exists.
        """
        try:
            distance_map = {
                "Cosine": Distance.COSINE,
                "Euclid": Distance.EUCLID,
                "Dot": Distance.DOT,
            }

            self._client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=vector_size,
                    distance=distance_map.get(distance, Distance.COSINE),
                ),
            )
            logger.info("qdrant.collection_created", collection=collection_name)
            return True
        except Exception as e:
            if "already exists" in str(e).lower():
                logger.debug("qdrant.collection_exists", collection=collection_name)
                return False
            logger.error("qdrant.create_collection_failed", collection=collection_name, error=str(e))
            raise

    async def upsert(
        self,
        collection_name: str,
        points: list[dict[str, Any]],
    ) -> bool:
        """
        Insert or update vectors in Qdrant.

        Args:
            collection_name: Target collection
            points: List of point dicts with 'id', 'vector', 'payload'

        Returns:
            True if successful.
        """
        collection = self._resolve_collection(collection_name)

        qdrant_points = [
            PointStruct(
                id=p["id"],
                vector=p["vector"],
                payload=p.get("payload", {}),
            )
            for p in points
        ]

        try:
            self._client.upsert(
                collection_name=collection,
                points=qdrant_points,
            )
            logger.info(
                "qdrant.upsert",
                collection=collection,
                points_count=len(qdrant_points),
            )
            return True
        except Exception as e:
            logger.error("qdrant.upsert_failed", collection=collection, error=str(e))
            raise

    async def search(
        self,
        collection_name: str,
        query_vector: list[float],
        limit: int = 10,
        filter_dict: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Search for similar vectors in Qdrant.

        Args:
            collection_name: Collection to search
            query_vector: Embedding vector to match
            limit: Maximum results
            filter_dict: Optional metadata filter

        Returns:
            List of matching points with scores.
        """
        collection = self._resolve_collection(collection_name)

        query_filter = None
        if filter_dict:
            conditions = []
            for key, value in filter_dict.items():
                conditions.append(
                    FieldCondition(
                        key=key,
                        match=MatchValue(value=value),
                    )
                )
            query_filter = Filter(must=conditions)

        try:
            results = self._client.search(
                collection_name=collection,
                query_vector=query_vector,
                limit=limit,
                query_filter=query_filter,
            )

            return [
                {
                    "id": str(hit.id),
                    "score": hit.score,
                    "payload": hit.payload or {},
                }
                for hit in results
            ]
        except Exception as e:
            logger.error("qdrant.search_failed", collection=collection, error=str(e))
            raise

    async def delete(
        self,
        collection_name: str,
        point_ids: list[str],
    ) -> bool:
        """
        Delete points by ID from Qdrant.

        Args:
            collection_name: Target collection
            point_ids: Point IDs to delete

        Returns:
            True if successful.
        """
        collection = self._resolve_collection(collection_name)

        try:
            self._client.delete(
                collection_name=collection,
                points_selector=point_ids,
            )
            logger.info("qdrant.delete", collection=collection, count=len(point_ids))
            return True
        except Exception as e:
            logger.error("qdrant.delete_failed", collection=collection, error=str(e))
            raise

    async def get_collection_info(self, collection_name: str) -> dict[str, Any]:
        """
        Get collection metadata from Qdrant.

        Args:
            collection_name: Collection name

        Returns:
            Collection info dict.
        """
        collection = self._resolve_collection(collection_name)

        try:
            info = self._client.get_collection(collection_name=collection)
            return {
                "name": collection,
                "vectors_count": info.vectors_count,
                "points_count": info.points_count,
                "config": str(info.config),
            }
        except Exception as e:
            logger.error("qdrant.get_info_failed", collection=collection, error=str(e))
            raise

    async def health_check(self) -> bool:
        """Check if Qdrant connection is alive."""
        try:
            self._client.get_collections()
            logger.info("qdrant.health_check", status="ok")
            return True
        except Exception as e:
            logger.error("qdrant.health_check_failed", error=str(e))
            return False
