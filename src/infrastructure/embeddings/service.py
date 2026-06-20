"""
Production embedding service — multi-provider with caching and batch processing.

Orchestrates embedding providers, caching, and Arabic text preprocessing
for optimal RAG retrieval quality.
"""

import asyncio
from typing import Any

import structlog

from src.config.settings import Settings
from src.infrastructure.embeddings.providers import (
    EmbeddingProvider,
    OpenAIEmbeddingProvider,
    JinaEmbeddingProvider,
    SentenceTransformerProvider,
    PlaceholderProvider,
)
from src.infrastructure.embeddings.cache import EmbeddingCache
from src.infrastructure.embeddings.preprocessing import (
    ArabicTextPreprocessor,
    arabic_preprocessor,
)

logger = structlog.get_logger(__name__)


class EmbeddingService:
    """
    Production embedding service.

    Features:
    - Multi-provider support (OpenAI, Jina, local, placeholder)
    - Redis-backed embedding cache
    - Arabic text preprocessing
    - Batch processing with rate limiting
    - Graceful fallback chain

    Provider selection priority:
    1. OpenAI (if OPENAI_API_KEY set)
    2. Jina (if JINA_API_KEY set)
    3. Local sentence-transformers (if EMBEDDING_LOCAL_MODEL set)
    4. Placeholder (always available, for dev/testing)
    """

    BATCH_SIZE = 100  # Max texts per API call
    BATCH_DELAY = 0.1  # Delay between batches (rate limiting)

    def __init__(
        self,
        settings: Settings,
        redis_client: Any = None,
    ) -> None:
        self._settings = settings
        self._preprocessor = arabic_preprocessor
        self._cache = EmbeddingCache(redis_client=redis_client)
        self._provider = self._create_provider()
        self._stats = {
            "total_embeds": 0,
            "cache_hits": 0,
            "api_calls": 0,
            "errors": 0,
        }

        logger.info(
            "embedding.service_init",
            provider=self._provider.name,
            dimension=self._provider.dimension,
            cache_enabled=True,
        )

    def _create_provider(self) -> EmbeddingProvider:
        """
        Create embedding provider based on configuration.

        Selection priority:
        1. OpenAI (if OPENAI_API_KEY set)
        2. Jina (if JINA_API_KEY set)
        3. Local (if EMBEDDING_LOCAL_MODEL set)
        4. Placeholder (fallback)
        """
        # 1. Try OpenAI
        openai_key = getattr(self._settings, "openai_api_key", None)
        if openai_key:
            try:
                return OpenAIEmbeddingProvider(
                    api_key=openai_key,
                    model=getattr(self._settings, "embedding_model", "text-embedding-3-small"),
                    base_url=getattr(self._settings, "openai_base_url", None),
                    dimensions=getattr(self._settings, "embedding_dimensions", 1536),
                )
            except Exception as e:
                logger.warning("embedding.openai_init_failed", error=str(e))

        # 2. Try Jina
        jina_key = getattr(self._settings, "jina_api_key", None)
        if jina_key:
            try:
                return JinaEmbeddingProvider(
                    api_key=jina_key,
                    model=getattr(self._settings, "jina_model", "jina-embeddings-v3"),
                    dimensions=getattr(self._settings, "embedding_dimensions", 1024),
                )
            except Exception as e:
                logger.warning("embedding.jina_init_failed", error=str(e))

        # 3. Try local sentence-transformers
        local_model = getattr(self._settings, "embedding_local_model", None)
        if local_model:
            try:
                return SentenceTransformerProvider(
                    model_name=local_model,
                    device=getattr(self._settings, "embedding_device", "cpu"),
                )
            except Exception as e:
                logger.warning("embedding.local_init_failed", error=str(e))

        # 4. Fallback to placeholder
        logger.warning("embedding.placeholder_fallback", reason="No embedding provider configured")
        return PlaceholderProvider()

    @property
    def provider_name(self) -> str:
        """Current provider name."""
        return self._provider.name

    @property
    def dimension(self) -> int:
        """Embedding vector dimension."""
        return self._provider.dimension

    @property
    def cache(self) -> EmbeddingCache:
        """Access the embedding cache."""
        return self._cache

    async def embed(self, text: str, use_cache: bool = True) -> list[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Text to embed
            use_cache: Whether to check/set cache

        Returns:
            Embedding vector.
        """
        self._stats["total_embeds"] += 1

        # Preprocess
        processed = self._preprocessor.preprocess_for_embedding(text)

        # Check cache
        if use_cache:
            cached = await self._cache.get(processed, self._provider.name)
            if cached is not None:
                self._stats["cache_hits"] += 1
                return cached

        # Generate embedding
        try:
            embedding = await self._provider.embed(processed)
            self._stats["api_calls"] += 1

            # Cache result
            if use_cache:
                await self._cache.set(processed, self._provider.name, embedding)

            return embedding
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(
                "embedding.embed_failed",
                provider=self._provider.name,
                error=str(e),
                text_preview=text[:50],
            )
            raise

    async def embed_batch(
        self,
        texts: list[str],
        use_cache: bool = True,
    ) -> list[list[float]]:
        """
        Generate embeddings for a batch of texts.

        Uses cache to avoid re-embedding, and processes in batches
        with rate limiting.

        Args:
            texts: List of texts to embed
            use_cache: Whether to check/set cache

        Returns:
            List of embedding vectors.
        """
        if not texts:
            return []

        self._stats["total_embeds"] += len(texts)

        # Preprocess all texts
        processed = [self._preprocessor.preprocess_for_embedding(t) for t in texts]

        # Check cache for all
        embeddings: list[list[float] | None] = [None] * len(texts)
        uncached_indices: list[int] = []

        if use_cache:
            misses, cached_results = await self._cache.get_batch(processed, self._provider.name)
            for i, result in enumerate(cached_results):
                embeddings[i] = result
            uncached_indices = misses
            self._stats["cache_hits"] += len(texts) - len(misses)
        else:
            uncached_indices = list(range(len(texts)))

        # Generate embeddings for uncached texts
        if uncached_indices:
            uncached_texts = [processed[i] for i in uncached_indices]

            try:
                # Process in batches with rate limiting
                batch_embeddings: list[list[float]] = []
                for i in range(0, len(uncached_texts), self.BATCH_SIZE):
                    batch = uncached_texts[i:i + self.BATCH_SIZE]
                    batch_result = await self._provider.embed_batch(batch)
                    batch_embeddings.extend(batch_result)
                    self._stats["api_calls"] += 1

                    # Rate limiting delay between batches
                    if i + self.BATCH_SIZE < len(uncached_texts):
                        await asyncio.sleep(self.BATCH_DELAY)

                # Fill in embeddings
                for idx, emb in zip(uncached_indices, batch_embeddings):
                    embeddings[idx] = emb

                # Cache new embeddings
                if use_cache:
                    uncached_texts_list = [processed[i] for i in uncached_indices]
                    await self._cache.set_batch(
                        uncached_texts_list,
                        self._provider.name,
                        batch_embeddings,
                    )

            except Exception as e:
                self._stats["errors"] += 1
                logger.error(
                    "embedding.batch_failed",
                    provider=self._provider.name,
                    batch_size=len(uncached_indices),
                    error=str(e),
                )
                raise

        # All embeddings should now be filled
        result = [emb for emb in embeddings if emb is not None]
        if len(result) != len(texts):
            logger.warning(
                "embedding.batch_partial",
                expected=len(texts),
                got=len(result),
            )

        return result

    async def health_check(self) -> dict[str, Any]:
        """
        Check embedding service health.

        Returns:
            Health status with provider info and stats.
        """
        provider_healthy = await self._provider.health_check()

        return {
            "status": "healthy" if provider_healthy else "degraded",
            "provider": self._provider.name,
            "dimension": self._provider.dimension,
            "cache_stats": self._cache.get_stats(),
            "service_stats": self._stats,
        }

    def get_stats(self) -> dict[str, Any]:
        """Get service statistics."""
        cache_stats = self._cache.get_stats()
        return {
            "provider": self._provider.name,
            "dimension": self._provider.dimension,
            "total_embeds": self._stats["total_embeds"],
            "api_calls": self._stats["api_calls"],
            "cache_hit_rate": cache_stats["hit_rate"],
            "errors": self._stats["errors"],
        }
