"""
Contextual compression — compress and extract relevant parts from context.

Extracts only the relevant portions from retrieved documents to fit
within LLM token limits while preserving important information.
"""

from typing import Any

import structlog

from src.agents.llm import llm_chat
from src.config.settings import Settings

logger = structlog.get_logger(__name__)

COMPRESSION_PROMPT = """You are a document compression expert for a retail/food company.

Given a user query and a document, extract ONLY the parts of the document
that are relevant to answering the query. Remove irrelevant information,
boilerplate, and redundant content.

Requirements:
1. Keep only information directly relevant to the query
2. Preserve important numbers, dates, and facts
3. Maintain the original language (Arabic or English)
4. Be concise but complete
5. If the document is not relevant at all, return "NOT_RELEVANT"

User Query: {query}

Document:
{document}

Compressed relevant content:"""


class ContextualCompressor:
    """
    LLM-based contextual compression for RAG context.

    Extracts relevant portions from retrieved documents to fit
    within token limits while preserving key information.
    """

    def __init__(
        self,
        settings: Settings,
        max_context_length: int = 4000,
    ) -> None:
        self._settings = settings
        self._max_context_length = max_context_length

    async def compress(
        self,
        query: str,
        documents: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Compress documents to extract relevant content.

        Args:
            query: User query
            documents: List of document dicts with 'payload' containing 'content'

        Returns:
            Compressed documents with extracted content.
        """
        compressed = []

        for doc in documents:
            content = doc.get("payload", {}).get("content", "")

            if not content:
                continue

            # Skip if already short enough
            if len(content) < 500:
                doc_copy = doc.copy()
                doc_copy["compressed_content"] = content
                compressed.append(doc_copy)
                continue

            try:
                prompt = COMPRESSION_PROMPT.format(query=query, document=content[:3000])
                result = await llm_chat(
                    settings=self._settings,
                    system_prompt="You are a document compression expert.",
                    user_message=prompt,
                    temperature=0.1,
                )

                if result.strip() != "NOT_RELEVANT":
                    doc_copy = doc.copy()
                    doc_copy["compressed_content"] = result.strip()
                    compressed.append(doc_copy)

            except Exception as e:
                logger.warning("compress.failed", error=str(e))
                # Include original if compression fails
                doc_copy = doc.copy()
                doc_copy["compressed_content"] = content[:1000]
                compressed.append(doc_copy)

        logger.info(
            "compress.compressed",
            input_count=len(documents),
            output_count=len(compressed),
        )

        return compressed

    async def compress_context(
        self,
        query: str,
        context: str,
    ) -> str:
        """
        Compress a context string to fit within token limits.

        Args:
            query: User query
            context: Full context string

        Returns:
            Compressed context string.
        """
        if len(context) <= self._max_context_length:
            return context

        try:
            prompt = COMPRESSION_PROMPT.format(
                query=query,
                document=context[:6000]  # Limit input size
            )
            result = await llm_chat(
                settings=self._settings,
                system_prompt="You are a document compression expert.",
                user_message=prompt,
                temperature=0.1,
            )

            if result.strip() and result.strip() != "NOT_RELEVANT":
                return result.strip()[:self._max_context_length]

            # Fallback: truncate
            return context[:self._max_context_length] + "\n\n[Truncated...]"

        except Exception as e:
            logger.warning("compress.context_failed", error=str(e))
            return context[:self._max_context_length] + "\n\n[Truncated...]"


class ExtractiveCompressor:
    """
    Extractive compression — extracts key sentences without LLM.

    Faster than LLM-based compression but less accurate.
    Uses sentence scoring based on query term overlap.
    """

    def __init__(self, max_length: int = 2000) -> None:
        self._max_length = max_length

    def _score_sentence(self, sentence: str, query_terms: set[str]) -> float:
        """Score a sentence based on query term overlap."""
        sentence_lower = sentence.lower()
        words = set(sentence_lower.split())
        overlap = len(words & query_terms)
        return overlap / len(words) if words else 0

    def compress(
        self,
        query: str,
        documents: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Compress documents using extractive method.

        Args:
            query: User query
            documents: List of document dicts

        Returns:
            Compressed documents with extracted sentences.
        """
        query_terms = set(query.lower().split())
        compressed = []

        for doc in documents:
            content = doc.get("payload", {}).get("content", "")
            if not content:
                continue

            # Split into sentences
            sentences = content.replace("\n", " ").split(". ")
            if not sentences:
                continue

            # Score sentences
            scored = [
                (s, self._score_sentence(s, query_terms))
                for s in sentences
                if len(s.strip()) > 10
            ]
            scored.sort(key=lambda x: x[1], reverse=True)

            # Select top sentences until max length
            selected = []
            current_length = 0
            for sentence, score in scored:
                if score > 0 and current_length + len(sentence) < self._max_length:
                    selected.append(sentence.strip())
                    current_length += len(sentence)

            if selected:
                doc_copy = doc.copy()
                doc_copy["compressed_content"] = ". ".join(selected) + "."
                compressed.append(doc_copy)

        return compressed


class CompressionRouter:
    """
    Routes compression requests to the appropriate compressor.

    Uses extractive compression for speed, LLM compression for quality.
    """

    def __init__(
        self,
        settings: Settings,
        use_llm: bool = True,
        max_context_length: int = 4000,
    ) -> None:
        self._llm_compressor = ContextualCompressor(settings, max_context_length) if use_llm else None
        self._extractive_compressor = ExtractiveCompressor(max_context_length)

    async def compress(
        self,
        query: str,
        documents: list[dict[str, Any]],
        use_llm: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Compress documents using the appropriate method.

        Args:
            query: User query
            documents: List of document dicts
            use_llm: Whether to use LLM compression

        Returns:
            Compressed documents.
        """
        if use_llm and self._llm_compressor:
            return await self._llm_compressor.compress(query, documents)
        else:
            return self._extractive_compressor.compress(query, documents)
