"""
RAG retriever — semantic search with embedding generation.

Wraps QdrantVectorStore for end-to-end semantic retrieval.

Phase 2: Uses EmbeddingService for real embedding generation.
Falls back to placeholder vectors when no embedding API is configured.
"""

from typing import Any

import structlog

from src.config.settings import Settings
from src.domain.interfaces.vector_store import VectorStoreInterface

logger = structlog.get_logger(__name__)


class Retriever:
    """
    Semantic retriever using Qdrant.

    Generates embeddings via EmbeddingService and searches Qdrant
    for semantically similar document chunks.
    """

    def __init__(
        self,
        vector_store: VectorStoreInterface,
        settings: Settings,
        embedding_service: Any = None,
    ) -> None:
        self._vector_store = vector_store
        self._settings = settings
        self._embedding_service = embedding_service

    async def _get_embedding(self, text: str) -> list[float]:
        """
        Generate embedding vector for text.

        Uses EmbeddingService if available, otherwise falls back to
        the embedding service's placeholder.

        Args:
            text: Text to embed

        Returns:
            Embedding vector (1536 dimensions).
        """
        if self._embedding_service is not None:
            return await self._embedding_service.embed(text)

        # Fallback: use embedding service default
        from src.infrastructure.rag.embeddings import EmbeddingService
        service = EmbeddingService(self._settings)
        self._embedding_service = service
        return await service.embed(text)

    async def retrieve(
        self,
        query: str,
        collection_name: str | None = None,
        limit: int = 5,
        filter_dict: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Retrieve relevant documents for a query.

        Args:
            query: User query text
            collection_name: Collection to search (default: company_docs)
            limit: Maximum results
            filter_dict: Optional metadata filter

        Returns:
            List of relevant document chunks with scores.
        """
        collection = collection_name or self._settings.qdrant_collection

        # Generate query embedding
        query_vector = await self._get_embedding(query)

        # Search Qdrant
        results = await self._vector_store.search(
            collection_name=collection,
            query_vector=query_vector,
            limit=limit,
            filter_dict=filter_dict,
        )

        logger.info(
            "retriever.search",
            query=query[:100],
            collection=collection,
            results_count=len(results),
        )

        return results

    async def retrieve_with_context(
        self,
        query: str,
        collection_name: str | None = None,
        limit: int = 5,
    ) -> str:
        """
        Retrieve and format documents as context string.

        Useful for injecting into LLM prompts.

        Args:
            query: User query
            collection_name: Collection to search
            limit: Maximum results

        Returns:
            Formatted context string.
        """
        results = await self.retrieve(query, collection_name, limit)

        if not results:
            return "No relevant documents found."

        context_parts: list[str] = []
        for i, r in enumerate(results, 1):
            content = r.get("payload", {}).get("content", "")
            score = r.get("score", 0)
            context_parts.append(f"[Document {i} | Score: {score:.2f}]\n{content}")

        return "\n\n---\n\n".join(context_parts)
