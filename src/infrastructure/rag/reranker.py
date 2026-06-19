"""
Reranking module — cross-encoder reranking for better relevance.

Reranks retrieved documents using more precise similarity scoring
to improve the quality of search results.
"""

from typing import Any

import structlog

from src.config.settings import Settings

logger = structlog.get_logger(__name__)


class CrossEncoderReranker:
    """
    Cross-encoder reranker for document relevance scoring.

    Uses a cross-encoder model to score query-document pairs
    for more accurate relevance ranking than bi-encoder similarity.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
    ) -> None:
        self._settings = settings
        self._model_name = model_name
        self._model = None
        self._initialized = False

    def _initialize(self) -> None:
        """Lazy-initialize the cross-encoder model."""
        if self._initialized:
            return

        try:
            from sentence_transformers import CrossEncoder
            self._model = CrossEncoder(self._model_name)
            self._initialized = True
            logger.info("reranker.initialized", model=self._model_name)
        except ImportError:
            logger.warning("reranker.missing_dep", dep="sentence-transformers")
        except Exception as e:
            logger.error("reranker.init_failed", error=str(e))

    async def rerank(
        self,
        query: str,
        documents: list[dict[str, Any]],
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Rerank documents using cross-encoder scoring.

        Args:
            query: Search query
            documents: List of document dicts with 'payload' containing 'content'
            top_k: Number of top results to return

        Returns:
            Reranked documents with cross-encoder scores.
        """
        self._initialize()

        if not documents:
            return []

        if self._model is None:
            # Fallback: return documents as-is
            logger.debug("reranker.fallback")
            return documents[:top_k]

        try:
            # Prepare query-document pairs
            pairs = []
            for doc in documents:
                content = doc.get("payload", {}).get("content", "")
                pairs.append([query, content])

            # Score with cross-encoder
            scores = self._model.predict(pairs)

            # Attach scores and sort
            scored_docs = []
            for doc, score in zip(documents, scores):
                doc_copy = doc.copy()
                doc_copy["rerank_score"] = float(score)
                scored_docs.append(doc_copy)

            # Sort by rerank score descending
            scored_docs.sort(key=lambda x: x["rerank_score"], reverse=True)

            # Return top_k
            results = scored_docs[:top_k]

            logger.info(
                "reranker.reranked",
                query=query[:100],
                input_count=len(documents),
                output_count=len(results),
            )

            return results

        except Exception as e:
            logger.error("reranker.rerank_failed", error=str(e))
            return documents[:top_k]


class MMRReranker:
    """
    Maximal Marginal Relevance (MMR) reranker.

    Balances relevance and diversity in search results to avoid
    returning too many similar documents.
    """

    def __init__(self, lambda_param: float = 0.7) -> None:
        """
        Args:
            lambda_param: Balance between relevance (1.0) and diversity (0.0)
        """
        self._lambda = lambda_param

    def _compute_similarity(self, vec1: list[float], vec2: list[float]) -> float:
        """Compute cosine similarity between two vectors."""
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = sum(a * a for a in vec1) ** 0.5
        norm2 = sum(b * b for b in vec2) ** 0.5

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)

    async def rerank(
        self,
        query: str,
        documents: list[dict[str, Any]],
        top_k: int = 5,
        query_embedding: list[float] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Rerank documents using MMR for diversity.

        Args:
            query: Search query
            documents: List of document dicts
            top_k: Number of top results to return
            query_embedding: Query embedding vector (optional)

        Returns:
            Reranked documents with MMR scores.
        """
        if not documents or len(documents) <= top_k:
            return documents

        # If no embeddings available, return as-is
        if query_embedding is None:
            return documents[:top_k]

        # Extract document embeddings (assuming stored in payload)
        doc_embeddings = []
        for doc in documents:
            embedding = doc.get("payload", {}).get("embedding")
            if embedding:
                doc_embeddings.append(embedding)
            else:
                doc_embeddings.append(None)

        # MMR selection
        selected: list[int] = []
        remaining = list(range(len(documents)))

        for _ in range(top_k):
            if not remaining:
                break

            best_idx = -1
            best_mmr = float("-inf")

            for idx in remaining:
                # Relevance score (cosine similarity to query)
                if doc_embeddings[idx] is not None:
                    relevance = self._compute_similarity(
                        query_embedding, doc_embeddings[idx]
                    )
                else:
                    # Use original score as fallback
                    relevance = documents[idx].get("score", 0)

                # Diversity score (max similarity to already selected)
                max_similarity = 0.0
                for sel_idx in selected:
                    if doc_embeddings[sel_idx] is not None and doc_embeddings[idx] is not None:
                        sim = self._compute_similarity(
                            doc_embeddings[idx], doc_embeddings[sel_idx]
                        )
                        max_similarity = max(max_similarity, sim)

                # MMR score
                mmr = self._lambda * relevance - (1 - self._lambda) * max_similarity

                if mmr > best_mmr:
                    best_mmr = mmr
                    best_idx = idx

            if best_idx >= 0:
                selected.append(best_idx)
                remaining.remove(best_idx)

        # Build results
        results = []
        for idx in selected:
            doc = documents[idx].copy()
            doc["mmr_score"] = doc.get("score", 0)
            results.append(doc)

        logger.info(
            "mmr.reranked",
            input_count=len(documents),
            output_count=len(results),
        )

        return results


class Reranker:
    """
    Unified reranker that combines cross-encoder and MMR.

    Provides a single interface for reranking search results.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        use_cross_encoder: bool = True,
        use_mmr: bool = True,
        mmr_lambda: float = 0.7,
    ) -> None:
        self._use_cross_encoder = use_cross_encoder
        self._use_mmr = use_mmr

        self._cross_encoder = CrossEncoderReranker(settings) if use_cross_encoder else None
        self._mmr = MMRReranker(mmr_lambda) if use_mmr else None

    async def rerank(
        self,
        query: str,
        documents: list[dict[str, Any]],
        top_k: int = 5,
        query_embedding: list[float] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Rerank documents using the configured reranking strategy.

        Args:
            query: Search query
            documents: List of document dicts
            top_k: Number of top results to return
            query_embedding: Query embedding for MMR (optional)

        Returns:
            Reranked documents.
        """
        results = documents

        # Step 1: Cross-encoder reranking
        if self._cross_encoder and results:
            results = await self._cross_encoder.rerank(
                query, results, top_k=top_k * 2  # Get more candidates for MMR
            )

        # Step 2: MMR for diversity
        if self._mmr and results and len(results) > top_k:
            results = await self._mmr.rerank(
                query, results, top_k, query_embedding
            )

        return results[:top_k]
