"""
Embedding service — generates vector embeddings for RAG.

Phase 1: Uses Groq-compatible embedding via OpenAI API (text-embedding-3-small).
Falls back to placeholder embeddings if no API key is configured.
"""

import hashlib
import struct
from typing import Any

import structlog

from src.config.settings import Settings

logger = structlog.get_logger(__name__)

EMBEDDING_DIM = 1536


def _placeholder_embedding(text: str) -> list[float]:
    """
    Generate a deterministic placeholder embedding from text.

    Uses SHA-512 hashing mapped to float vectors. NOT semantically
    meaningful — only used so the pipeline runs without an embedding API.
    Replace with a real embedding model in production.
    """
    h = hashlib.sha512(text.encode("utf-8")).digest()
    vec: list[float] = []
    for i in range(0, min(len(h), EMBEDDING_DIM * 4), 4):
        chunk = h[i : i + 4] if i + 4 <= len(h) else h[i:].ljust(4, b"\x00")
        val = struct.unpack(">f", chunk)[0]
        val = max(-1.0, min(1.0, val / 1e38))
        vec.append(val)
    while len(vec) < EMBEDDING_DIM:
        vec.append(0.0)
    return vec[:EMBEDDING_DIM]


class EmbeddingService:
    """
    Embedding service for generating text vectors.

    Uses OpenAI-compatible embedding API (works with OpenAI, Jina, Voyage).
    Falls back to placeholder vectors when no embedding API is configured.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: Any = None
        self._use_placeholder = not settings.groq_api_key

        if not self._use_placeholder:
            try:
                import openai
                self._client = openai.AsyncOpenAI(
                    api_key=settings.groq_api_key,
                    base_url=settings.groq_base_url,
                )
                logger.info("embedding.service_initialized", mode="api")
            except Exception as e:
                logger.warning("embedding.api_init_failed", error=str(e))
                self._use_placeholder = True

        if self._use_placeholder:
            logger.warning("embedding.placeholder_mode", reason="No embedding API configured")

    async def embed(self, text: str) -> list[float]:
        """
        Generate embedding vector for a single text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector (1536 dimensions).
        """
        if self._use_placeholder or self._client is None:
            return _placeholder_embedding(text)

        try:
            response = await self._client.embeddings.create(
                model="text-embedding-3-small",
                input=text[:8000],  # Truncate for API limits
            )
            return response.data[0].embedding
        except Exception as e:
            logger.warning("embedding.api_failed", error=str(e))
            return _placeholder_embedding(text)

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embedding vectors for multiple texts.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors.
        """
        if self._use_placeholder or self._client is None:
            return [_placeholder_embedding(t) for t in texts]

        try:
            # Truncate texts for API limits
            truncated = [t[:8000] for t in texts]
            response = await self._client.embeddings.create(
                model="text-embedding-3-small",
                input=truncated,
            )
            return [item.embedding for item in response.data]
        except Exception as e:
            logger.warning("embedding.batch_api_failed", error=str(e))
            return [_placeholder_embedding(t) for t in texts]
