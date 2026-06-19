"""
Abstract interface for vector store (Qdrant).

Domain layer depends only on this interface. The infrastructure layer
implements the concrete Qdrant client.
"""

from abc import ABC, abstractmethod
from typing import Any


class VectorStoreInterface(ABC):
    """Abstract vector store contract."""

    @abstractmethod
    async def create_collection(
        self,
        collection_name: str,
        vector_size: int = 1536,
        distance: str = "Cosine",
    ) -> bool:
        """
        Create a new collection in the vector store.

        Args:
            collection_name: Name of the collection
            vector_size: Dimension of embedding vectors
            distance: Distance metric (Cosine, Euclid, Dot)

        Returns:
            True if created, False if already exists.
        """
        ...

    @abstractmethod
    async def upsert(
        self,
        collection_name: str,
        points: list[dict[str, Any]],
    ) -> bool:
        """
        Insert or update vectors in the collection.

        Args:
            collection_name: Target collection
            points: List of point dicts with id, vector, payload

        Returns:
            True if successful.
        """
        ...

    @abstractmethod
    async def search(
        self,
        collection_name: str,
        query_vector: list[float],
        limit: int = 10,
        filter_dict: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Search for similar vectors.

        Args:
            collection_name: Collection to search
            query_vector: Embedding vector to match against
            limit: Maximum results
            filter_dict: Optional metadata filter

        Returns:
            List of matching points with scores.
        """
        ...

    @abstractmethod
    async def delete(
        self,
        collection_name: str,
        point_ids: list[str],
    ) -> bool:
        """
        Delete points by ID.

        Args:
            collection_name: Target collection
            point_ids: List of point IDs to delete

        Returns:
            True if successful.
        """
        ...

    @abstractmethod
    async def get_collection_info(self, collection_name: str) -> dict[str, Any]:
        """
        Get collection metadata and stats.

        Args:
            collection_name: Collection name

        Returns:
            Collection info dict (vectors count, config, etc.)
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if vector store connection is alive."""
        ...
