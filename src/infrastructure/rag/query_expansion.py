"""
Query expansion — LLM-based query reformulation for better recall.

Expands and reformulates user queries to improve retrieval quality
by generating multiple search variants.
"""

from typing import Any

import structlog

from src.agents.llm import llm_chat
from src.config.settings import Settings

logger = structlog.get_logger(__name__)

QUERY_EXPANSION_PROMPT = """You are a search query expansion expert for a retail/food company.

Given a user query, generate 3-5 alternative search queries that would find
relevant documents. The queries should:
1. Capture different phrasings of the same intent
2. Include relevant synonyms and related terms
3. Be in the same language as the original query (Arabic or English)
4. Be concise and search-focused

Return ONLY a JSON array of strings, no explanations.
Example: ["query1", "query2", "query3"]

User Query: {query}"""

QUERY_REWRITE_PROMPT = """You are a search query rewriter for a retail/food company.

Rewrite the following user query to be more effective for document retrieval.
The rewritten query should:
1. Be more specific and precise
2. Remove conversational filler
3. Focus on key entities and concepts
4. Be in the same language as the original

Return ONLY the rewritten query text, no explanations.

User Query: {query}"""


class QueryExpander:
    """
    LLM-based query expansion for better RAG retrieval.

    Generates multiple search variants from a single user query
    to improve recall and coverage.
    """

    def __init__(
        self,
        settings: Settings,
        max_expansions: int = 5,
        use_rewrite: bool = True,
    ) -> None:
        self._settings = settings
        self._max_expansions = max_expansions
        self._use_rewrite = use_rewrite

    async def expand(self, query: str) -> list[str]:
        """
        Expand a query into multiple search variants.

        Args:
            query: Original user query

        Returns:
            List of expanded queries (including original)
        """
        queries = [query]  # Always include original

        try:
            # Get LLM expansions
            prompt = QUERY_EXPANSION_PROMPT.format(query=query)
            response = await llm_chat(
                settings=self._settings,
                system_prompt="You are a search query expansion expert.",
                user_message=prompt,
                temperature=0.3,
            )

            # Parse JSON array from response
            import json
            import re

            # Try to extract JSON array from response
            json_match = re.search(r'\[.*?\]', response, re.DOTALL)
            if json_match:
                expansions = json.loads(json_match.group())
                queries.extend(expansions[:self._max_expansions - 1])

            logger.info(
                "query_expander.expanded",
                original=query[:50],
                expansions=len(queries),
            )

        except Exception as e:
            logger.warning("query_expander.failed", error=str(e))

        return queries

    async def rewrite(self, query: str) -> str:
        """
        Rewrite a query for better retrieval.

        Args:
            query: Original user query

        Returns:
            Rewritten query
        """
        if not self._use_rewrite:
            return query

        try:
            prompt = QUERY_REWRITE_PROMPT.format(query=query)
            rewritten = await llm_chat(
                settings=self._settings,
                system_prompt="You are a search query rewriter.",
                user_message=prompt,
                temperature=0.2,
            )

            # Clean up the response
            rewritten = rewritten.strip().strip('"').strip("'")

            if rewritten and rewritten != query:
                logger.info(
                    "query_expander.rewritten",
                    original=query[:50],
                    rewritten=rewritten[:50],
                )
                return rewritten

            return query

        except Exception as e:
            logger.warning("query_expander.rewrite_failed", error=str(e))
            return query

    async def expand_and_rewrite(self, query: str) -> tuple[str, list[str]]:
        """
        Rewrite query and generate expansions.

        Args:
            query: Original user query

        Returns:
            Tuple of (rewritten_query, expansion_queries)
        """
        rewritten = await self.rewrite(query)
        expansions = await self.expand(rewritten)

        return rewritten, expansions


class MultiQuerySearcher:
    """
    Multi-query searcher that combines results from multiple query variants.

    Uses query expansion to retrieve documents from different angles,
    then merges and deduplicates results.
    """

    def __init__(
        self,
        settings: Settings,
        max_queries: int = 3,
    ) -> None:
        self._expander = QueryExpander(settings, max_expansions=max_queries)

    async def search(
        self,
        query: str,
        search_fn: Any,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Search using multiple query variants.

        Args:
            query: Original user query
            search_fn: Async search function(query, limit) -> results
            limit: Maximum results per query

        Returns:
            Merged and deduplicated results.
        """
        # Get query variants
        rewritten, expansions = await self._expander.expand_and_rewrite(query)

        # Combine all queries
        all_queries = [rewritten] + [q for q in expansions if q != rewritten]

        # Search with each query
        all_results: list[dict[str, Any]] = []
        seen_ids: set[str] = set()

        for q in all_queries[:3]:  # Limit to 3 queries
            try:
                results = await search_fn(q, limit=limit)
                for r in results:
                    doc_id = r.get("id", "")
                    if doc_id and doc_id not in seen_ids:
                        seen_ids.add(doc_id)
                        r["source_query"] = q
                        all_results.append(r)
            except Exception as e:
                logger.warning("multi_query.search_failed", query=q[:50], error=str(e))

        # Sort by score
        all_results.sort(key=lambda x: x.get("score", 0), reverse=True)

        logger.info(
            "multi_query.searched",
            original=query[:50],
            queries_used=len(all_queries),
            total_results=len(all_results),
        )

        return all_results[:limit]
