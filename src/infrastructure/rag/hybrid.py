"""
Hybrid search — combines semantic (vector) + keyword (BM25) search.

Uses Reciprocal Rank Fusion (RRF) to merge results from both search
methods for better retrieval quality.
"""

import math
from collections import defaultdict
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class BM25Index:
    """
    Simple BM25 index for keyword search.

    Implements Okapi BM25 scoring for text retrieval.
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self._k1 = k1
        self._b = b
        self._documents: list[dict[str, Any]] = []
        self._doc_lengths: list[int] = []
        self._avg_doc_length: float = 0.0
        self._term_freqs: list[dict[str, int]] = []
        self._inverse_doc_freq: dict[str, float] = {}

    def _tokenize(self, text: str) -> list[str]:
        """Simple tokenization for Arabic and English text."""
        import re
        # Lowercase and split on non-alphanumeric
        text = text.lower()
        # Keep Arabic and English characters
        tokens = re.findall(r'[\u0600-\u06FF\u0750-\u077Fa-z0-9]+', text)
        return tokens

    def _build_index(self) -> None:
        """Build BM25 index from documents."""
        # Count term frequencies per document
        self._term_freqs = []
        doc_freq: dict[str, int] = defaultdict(int)

        for doc in self._documents:
            content = doc.get("payload", {}).get("content", "")
            tokens = self._tokenize(content)
            tf: dict[str, int] = defaultdict(int)
            for token in tokens:
                tf[token] += 1
            self._term_freqs.append(dict(tf))
            self._doc_lengths.append(len(tokens))

            # Update document frequency
            unique_tokens = set(tokens)
            for token in unique_tokens:
                doc_freq[token] += 1

        # Calculate average document length
        self._avg_doc_length = (
            sum(self._doc_lengths) / len(self._doc_lengths)
            if self._doc_lengths else 1.0
        )

        # Calculate IDF
        n_docs = len(self._documents)
        for term, df in doc_freq.items():
            self._inverse_doc_freq[term] = math.log(
                (n_docs - df + 0.5) / (df + 0.5) + 1
            )

    def index(self, documents: list[dict[str, Any]]) -> None:
        """
        Index documents for BM25 search.

        Args:
            documents: List of document dicts with 'payload' containing 'content'
        """
        self._documents = documents
        self._build_index()
        logger.info("bm25.indexed", count=len(documents))

    def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """
        Search documents using BM25 scoring.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of documents with BM25 scores.
        """
        if not self._documents:
            return []

        query_tokens = self._tokenize(query)
        scores: list[tuple[int, float]] = []

        for i, doc in enumerate(self._documents):
            score = 0.0
            doc_length = self._doc_lengths[i]
            tf = self._term_freqs[i]

            for token in query_tokens:
                if token in tf:
                    term_freq = tf[token]
                    idf = self._inverse_doc_freq.get(token, 0)

                    # BM25 scoring formula
                    numerator = term_freq * (self._k1 + 1)
                    denominator = term_freq + self._k1 * (
                        1 - self._b + self._b * doc_length / self._avg_doc_length
                    )
                    score += idf * numerator / denominator

            if score > 0:
                scores.append((i, score))

        # Sort by score descending
        scores.sort(key=lambda x: x[1], reverse=True)

        # Return top results
        results = []
        for idx, bm25_score in scores[:limit]:
            doc = self._documents[idx].copy()
            doc["bm25_score"] = bm25_score
            results.append(doc)

        return results


def reciprocal_rank_fusion(
    result_lists: list[list[dict[str, Any]]],
    k: int = 60,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """
    Merge multiple result lists using Reciprocal Rank Fusion (RRF).

    RRF combines rankings from different search methods by computing
    a fusion score based on the rank of each document across all lists.

    Args:
        result_lists: List of result lists to merge
        k: RRF constant (default 60, as per original paper)
        limit: Maximum results to return

    Returns:
        Merged and ranked results.
    """
    # Calculate RRF scores
    doc_scores: dict[str, float] = defaultdict(float)
    doc_data: dict[str, dict[str, Any]] = {}

    for results in result_lists:
        for rank, doc in enumerate(results):
            doc_id = doc.get("id", str(rank))
            # RRF formula: 1 / (k + rank)
            rrf_score = 1.0 / (k + rank + 1)
            doc_scores[doc_id] += rrf_score
            doc_data[doc_id] = doc

    # Sort by RRF score
    sorted_docs = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)

    # Build merged results
    results = []
    for doc_id, rrf_score in sorted_docs[:limit]:
        doc = doc_data[doc_id].copy()
        doc["rrf_score"] = rrf_score
        results.append(doc)

    return results


class HybridSearcher:
    """
    Hybrid search combining semantic (vector) and keyword (BM25) search.

    Provides better retrieval by combining the strengths of both approaches:
    - Semantic search: captures meaning and context
    - BM25: captures exact keyword matches and rare terms
    """

    def __init__(self) -> None:
        self._bm25 = BM25Index()
        self._documents: list[dict[str, Any]] = []

    def index_documents(self, documents: list[dict[str, Any]]) -> None:
        """
        Index documents for hybrid search.

        Args:
            documents: List of document dicts with 'payload' containing 'content'
        """
        self._documents = documents
        self._bm25.index(documents)
        logger.info("hybrid.indexed", count=len(documents))

    async def search(
        self,
        query: str,
        semantic_search_fn: Any,
        limit: int = 10,
        semantic_weight: float = 0.7,
        keyword_weight: float = 0.3,
    ) -> list[dict[str, Any]]:
        """
        Perform hybrid search combining semantic and keyword results.

        Args:
            query: Search query
            semantic_search_fn: Async function for semantic search
            limit: Maximum results
            semantic_weight: Weight for semantic results (0-1)
            keyword_weight: Weight for keyword results (0-1)

        Returns:
            Merged and ranked results.
        """
        # Semantic search
        semantic_results = []
        try:
            semantic_results = await semantic_search_fn(query, limit=limit * 2)
        except Exception as e:
            logger.warning("hybrid.semantic_failed", error=str(e))

        # BM25 search
        bm25_results = self._bm25.search(query, limit=limit * 2)

        # Merge using RRF
        if semantic_results and bm25_results:
            merged = reciprocal_rank_fusion(
                [semantic_results, bm25_results],
                limit=limit,
            )
        elif semantic_results:
            merged = semantic_results[:limit]
        elif bm25_results:
            merged = bm25_results[:limit]
        else:
            merged = []

        logger.info(
            "hybrid.search",
            query=query[:100],
            semantic_count=len(semantic_results),
            bm25_count=len(bm25_results),
            merged_count=len(merged),
        )

        return merged
