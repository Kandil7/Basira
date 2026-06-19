"""
Advanced RAG retriever — combines hybrid search, reranking, query expansion,
and contextual compression for production-quality retrieval.
"""

from typing import Any

import structlog

from src.config.settings import Settings
from src.domain.interfaces.vector_store import VectorStoreInterface
from src.infrastructure.rag.embeddings import EmbeddingService
from src.infrastructure.rag.hybrid import HybridSearcher
from src.infrastructure.rag.reranker import Reranker
from src.infrastructure.rag.query_expansion import MultiQuerySearcher
from src.infrastructure.rag.compression import CompressionRouter

logger = structlog.get_logger(__name__)


class AdvancedRetriever:
    """
    Production-grade RAG retriever combining multiple retrieval strategies.

    Pipeline:
    1. Query expansion (optional)
    2. Hybrid search (semantic + BM25)
    3. Reranking (cross-encoder + MMR)
    4. Contextual compression (optional)
    """

    def __init__(
        self,
        vector_store: VectorStoreInterface,
        settings: Settings,
        embedding_service: EmbeddingService | None = None,
        enable_query_expansion: bool = True,
        enable_hybrid_search: bool = True,
        enable_reranking: bool = True,
        enable_compression: bool = True,
    ) -> None:
        self._vector_store = vector_store
        self._settings = settings
        self._embedding_service = embedding_service
        self._enable_query_expansion = enable_query_expansion
        self._enable_hybrid_search = enable_hybrid_search
        self._enable_reranking = enable_reranking
        self._enable_compression = enable_compression

        # Initialize components
        self._hybrid = HybridSearcher() if enable_hybrid_search else None
        self._reranker = Reranker(settings) if enable_reranking else None
        self._multi_query = MultiQuerySearcher(settings) if enable_query_expansion else None
        self._compressor = CompressionRouter(settings) if enable_compression else None

        # Embedding cache for hybrid search
        self._documents_indexed = False

    async def _get_embedding(self, text: str) -> list[float]:
        """Generate embedding vector for text."""
        if self._embedding_service:
            return await self._embedding_service.embed(text)

        from src.infrastructure.rag.embeddings import EmbeddingService
        service = EmbeddingService(self._settings)
        self._embedding_service = service
        return await service.embed(text)

    async def _semantic_search(
        self,
        query: str,
        collection: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        """Perform semantic search."""
        query_vector = await self._get_embedding(query)
        return await self._vector_store.search(
            collection_name=collection,
            query_vector=query_vector,
            limit=limit,
        )

    async def retrieve(
        self,
        query: str,
        collection_name: str | None = None,
        limit: int = 10,
        filter_dict: dict[str, Any] | None = None,
        enable_compression: bool | None = None,
    ) -> list[dict[str, Any]]:
        """
        Advanced retrieval pipeline.

        Args:
            query: User query
            collection_name: Collection to search
            limit: Maximum results
            filter_dict: Optional metadata filter
            enable_compression: Override compression setting

        Returns:
            Retrieved and processed documents.
        """
        collection = collection_name or self._settings.qdrant_collection
        use_compression = enable_compression if enable_compression is not None else self._enable_compression

        # Step 1: Query expansion (uses multi-query for better coverage)
        if self._enable_query_expansion and self._multi_query:
            results = await self._multi_query.search(
                query=query,
                search_fn=lambda q, lim: self._semantic_search(q, collection, lim),
                limit=limit * 2,
            )
        else:
            results = await self._semantic_search(query, collection, limit * 2)

        # Step 2: Hybrid search (add BM25 results if enabled)
        if self._enable_hybrid_search and self._hybrid and results:
            # Index documents for BM25
            if not self._documents_indexed:
                # Get a batch for indexing
                all_docs = await self._semantic_search(query, collection, 100)
                self._hybrid.index_documents(all_docs)
                self._documents_indexed = True

            hybrid_results = await self._hybrid.search(
                query=query,
                semantic_search_fn=lambda q, lim: self._semantic_search(q, collection, lim),
                limit=limit * 2,
            )
            # Merge with existing results
            seen_ids = {r.get("id") for r in results}
            for r in hybrid_results:
                if r.get("id") not in seen_ids:
                    results.append(r)

        # Step 3: Reranking
        if self._enable_reranking and self._reranker and results:
            query_embedding = await self._get_embedding(query)
            results = await self._reranker.rerank(
                query=query,
                documents=results,
                top_k=limit,
                query_embedding=query_embedding,
            )

        # Step 4: Compression
        if use_compression and self._compressor and results:
            results = await self._compressor.compress(query, results)

        # Apply filter if provided
        if filter_dict:
            results = [
                r for r in results
                if all(
                    r.get("payload", {}).get(k) == v
                    for k, v in filter_dict.items()
                )
            ]

        logger.info(
            "advanced_retrieve.completed",
            query=query[:100],
            results_count=len(results),
            pipeline="expanded+hybrid+reranked" if all([
                self._enable_query_expansion,
                self._enable_hybrid_search,
                self._enable_reranking,
            ]) else "basic",
        )

        return results[:limit]

    async def retrieve_with_context(
        self,
        query: str,
        collection_name: str | None = None,
        limit: int = 5,
    ) -> str:
        """
        Retrieve and format documents as context string.

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
            content = r.get("compressed_content") or r.get("payload", {}).get("content", "")
            score = r.get("rrf_score") or r.get("rerank_score") or r.get("score", 0)
            context_parts.append(f"[Document {i} | Score: {score:.2f}]\n{content}")

        return "\n\n---\n\n".join(context_parts)
