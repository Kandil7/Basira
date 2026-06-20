"""
Embedding cache — Redis-backed cache for embedding vectors.

Avoids re-embedding identical text, saving API costs and latency.
Supports TTL-based expiration and cache statistics.
"""

import json
import hashlib
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class EmbeddingCache:
    """
    Redis-backed embedding cache.

    Caches embedding vectors keyed by text hash, with configurable TTL.
    Falls back to in-memory cache when Redis is unavailable.
    """

    DEFAULT_TTL = 86400 * 7  # 7 days

    def __init__(
        self,
        redis_client: Any = None,
        ttl: int = DEFAULT_TTL,
        prefix: str = "emb:",
    ) -> None:
        self._redis = redis_client
        self._ttl = ttl
        self._prefix = prefix
        self._memory_cache: dict[str, list[float]] = {}
        self._stats = {"hits": 0, "misses": 0, "errors": 0}

    def _make_key(self, text: str, model: str) -> str:
        """Generate cache key from text and model."""
        content = f"{model}:{text}"
        hash_val = hashlib.sha256(content.encode("utf-8")).hexdigest()[:32]
        return f"{self._prefix}{hash_val}"

    async def get(self, text: str, model: str) -> list[float] | None:
        """
        Get cached embedding for text.

        Args:
            text: Input text
            model: Embedding model name

        Returns:
            Cached embedding vector, or None if not found.
        """
        key = self._make_key(text, model)

        # Try Redis first
        if self._redis is not None:
            try:
                cached = await self._redis.get(key)
                if cached:
                    self._stats["hits"] += 1
                    return json.loads(cached)
            except Exception as e:
                self._stats["errors"] += 1
                logger.warning("embedding.cache.redis_get_error", error=str(e))

        # Fallback to memory cache
        if key in self._memory_cache:
            self._stats["hits"] += 1
            return self._memory_cache[key]

        self._stats["misses"] += 1
        return None

    async def set(
        self,
        text: str,
        model: str,
        embedding: list[float],
        ttl: int | None = None,
    ) -> None:
        """
        Cache an embedding vector.

        Args:
            text: Input text
            model: Embedding model name
            embedding: Embedding vector to cache
            ttl: Time-to-live in seconds (uses default if None)
        """
        key = self._make_key(text, model)
        ttl = ttl or self._ttl
        value = json.dumps(embedding)

        # Try Redis
        if self._redis is not None:
            try:
                await self._redis.setex(key, ttl, value)
            except Exception as e:
                logger.warning("embedding.cache.redis_set_error", error=str(e))

        # Also store in memory
        self._memory_cache[key] = embedding

    async def get_batch(
        self,
        texts: list[str],
        model: str,
    ) -> tuple[list[int], list[list[float] | None]]:
        """
        Get cached embeddings for a batch of texts.

        Args:
            texts: List of input texts
            model: Embedding model name

        Returns:
            Tuple of (indices_of_misses, list_of_embeddings_or_none)
            where embeddings[i] corresponds to texts[i].
        """
        results: list[list[float] | None] = []
        misses: list[int] = []

        for i, text in enumerate(texts):
            cached = await self.get(text, model)
            results.append(cached)
            if cached is None:
                misses.append(i)

        hit_rate = (len(texts) - len(misses)) / len(texts) if texts else 0
        logger.debug(
            "embedding.cache.batch_lookup",
            total=len(texts),
            hits=len(texts) - len(misses),
            misses=len(misses),
            hit_rate=f"{hit_rate:.1%}",
        )

        return misses, results

    async def set_batch(
        self,
        texts: list[str],
        model: str,
        embeddings: list[list[float]],
        ttl: int | None = None,
    ) -> None:
        """
        Cache a batch of embeddings.

        Args:
            texts: List of input texts
            model: Embedding model name
            embeddings: List of embedding vectors
            ttl: Time-to-live in seconds
        """
        for text, embedding in zip(texts, embeddings):
            await self.set(text, model, embedding, ttl)

    async def invalidate(self, text: str, model: str) -> bool:
        """Remove a cached embedding."""
        key = self._make_key(text, model)

        removed = False
        if self._redis is not None:
            try:
                await self._redis.delete(key)
                removed = True
            except Exception as e:
                logger.warning("embedding.cache.redis_delete_error", error=str(e))

        if key in self._memory_cache:
            del self._memory_cache[key]
            removed = True

        return removed

    async def clear(self) -> int:
        """Clear all cached embeddings. Returns count of cleared entries."""
        count = 0

        # Clear memory cache
        count = len(self._memory_cache)
        self._memory_cache.clear()

        # Clear Redis keys with prefix
        if self._redis is not None:
            try:
                cursor = 0
                while True:
                    cursor, keys = await self._redis.scan(
                        cursor=cursor,
                        match=f"{self._prefix}*",
                        count=100,
                    )
                    if keys:
                        await self._redis.delete(*keys)
                        count += len(keys)
                    if cursor == 0:
                        break
            except Exception as e:
                logger.warning("embedding.cache.redis_clear_error", error=str(e))

        self._stats = {"hits": 0, "misses": 0, "errors": 0}
        logger.info("embedding.cache.cleared", count=count)
        return count

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        total = self._stats["hits"] + self._stats["misses"]
        return {
            **self._stats,
            "total_requests": total,
            "hit_rate": self._stats["hits"] / total if total > 0 else 0,
            "memory_entries": len(self._memory_cache),
        }
