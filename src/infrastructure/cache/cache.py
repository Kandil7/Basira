"""
Core cache implementations — in-memory LRU, Redis, and multi-tier.

MultiTierCache combines L1 (fast, small) and L2 (persistent, large)
for optimal performance and persistence.
"""

import asyncio
import hashlib
import json
import time
from collections import OrderedDict
from typing import Any, Callable

import structlog

logger = structlog.get_logger(__name__)


class CacheStats:
    """Track cache statistics for monitoring."""

    def __init__(self) -> None:
        self.hits = 0
        self.misses = 0
        self.errors = 0
        self.sets = 0
        self.deletes = 0
        self.evictions = 0

    def record_hit(self) -> None:
        self.hits += 1

    def record_miss(self) -> None:
        self.misses += 1

    def record_error(self) -> None:
        self.errors += 1

    def record_set(self) -> None:
        self.sets += 1

    def record_delete(self) -> None:
        self.deletes += 1

    def record_eviction(self) -> None:
        self.evictions += 1

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    def get_stats(self) -> dict[str, Any]:
        return {
            "hits": self.hits,
            "misses": self.misses,
            "errors": self.errors,
            "sets": self.sets,
            "deletes": self.deletes,
            "evictions": self.evictions,
            "hit_rate": round(self.hit_rate, 4),
        }

    def reset(self) -> None:
        self.hits = 0
        self.misses = 0
        self.errors = 0
        self.sets = 0
        self.deletes = 0
        self.evictions = 0


class LRUCache:
    """
    In-memory LRU cache with TTL support.

    Used as L1 cache in MultiTierCache for sub-millisecond reads.
    """

    def __init__(self, max_size: int = 1000, default_ttl: int = 300) -> None:
        """
        Args:
            max_size: Maximum number of entries
            default_ttl: Default TTL in seconds
        """
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._stats = CacheStats()

    def get(self, key: str) -> Any | None:
        """Get value by key, returns None if missing or expired."""
        if key in self._cache:
            value, expires_at = self._cache[key]
            if expires_at > time.time():
                # Move to end (most recently used)
                self._cache.move_to_end(key)
                self._stats.record_hit()
                return value
            else:
                # Expired
                del self._cache[key]
                self._stats.record_eviction()

        self._stats.record_miss()
        return None

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Set value with optional TTL."""
        ttl = ttl or self._default_ttl
        expires_at = time.time() + ttl

        if key in self._cache:
            self._cache.move_to_end(key)
        else:
            # Evict if at capacity
            while len(self._cache) >= self._max_size:
                self._cache.popitem(last=False)
                self._stats.record_eviction()

        self._cache[key] = (value, expires_at)
        self._stats.record_set()

    def delete(self, key: str) -> bool:
        """Delete a key. Returns True if deleted."""
        if key in self._cache:
            del self._cache[key]
            self._stats.record_delete()
            return True
        return False

    def clear(self) -> int:
        """Clear all entries. Returns count cleared."""
        count = len(self._cache)
        self._cache.clear()
        return count

    def cleanup_expired(self) -> int:
        """Remove all expired entries. Returns count removed."""
        now = time.time()
        expired = [k for k, (_, exp) in self._cache.items() if exp <= now]
        for k in expired:
            del self._cache[k]
        return len(expired)

    @property
    def size(self) -> int:
        return len(self._cache)

    @property
    def stats(self) -> CacheStats:
        return self._stats

    def get_keys(self) -> list[str]:
        """Get all cache keys."""
        return list(self._cache.keys())


class RedisCache:
    """
    Redis-backed cache with async operations.

    Used as L2 cache in MultiTierCache for persistence and shared state.
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        prefix: str = "cache:",
        default_ttl: int = 3600,
    ) -> None:
        self._redis_url = redis_url
        self._prefix = prefix
        self._default_ttl = default_ttl
        self._redis = None
        self._connected = False
        self._stats = CacheStats()

        self._connect()

    def _connect(self) -> None:
        """Initialize Redis connection."""
        try:
            import redis.asyncio as aioredis

            self._redis = aioredis.from_url(
                self._redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
            )
            self._connected = True
            logger.info("cache.redis_connected", url=self._redis_url)
        except ImportError:
            logger.warning("cache.redis_missing_dep", dep="redis")
        except Exception as e:
            logger.warning("cache.redis_connection_failed", error=str(e))

    def _make_key(self, key: str) -> str:
        """Add prefix to key."""
        return f"{self._prefix}{key}"

    async def get(self, key: str) -> Any | None:
        """Get value by key."""
        if not self._connected or self._redis is None:
            self._stats.record_miss()
            return None

        try:
            full_key = self._make_key(key)
            data = await self._redis.get(full_key)
            if data:
                self._stats.record_hit()
                return json.loads(data)
            self._stats.record_miss()
            return None
        except Exception as e:
            self._stats.record_error()
            logger.warning("cache.redis_get_error", key=key, error=str(e))
            return None

    async def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
        """Set value with optional TTL."""
        if not self._connected or self._redis is None:
            return False

        ttl = ttl or self._default_ttl
        try:
            full_key = self._make_key(key)
            serialized = json.dumps(value, ensure_ascii=False, default=str)
            await self._redis.setex(full_key, ttl, serialized)
            self._stats.record_set()
            return True
        except Exception as e:
            self._stats.record_error()
            logger.warning("cache.redis_set_error", key=key, error=str(e))
            return False

    async def delete(self, key: str) -> bool:
        """Delete a key."""
        if not self._connected or self._redis is None:
            return False

        try:
            full_key = self._make_key(key)
            await self._redis.delete(full_key)
            self._stats.record_delete()
            return True
        except Exception as e:
            self._stats.record_error()
            logger.warning("cache.redis_delete_error", key=key, error=str(e))
            return False

    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern."""
        if not self._connected or self._redis is None:
            return 0

        try:
            full_pattern = self._make_key(pattern)
            cursor = 0
            deleted = 0
            while True:
                cursor, keys = await self._redis.scan(
                    cursor=cursor,
                    match=full_pattern,
                    count=100,
                )
                if keys:
                    await self._redis.delete(*keys)
                    deleted += len(keys)
                if cursor == 0:
                    break
            self._stats.record_delete()
            return deleted
        except Exception as e:
            self._stats.record_error()
            logger.warning("cache.redis_delete_pattern_error", error=str(e))
            return 0

    async def clear(self) -> int:
        """Clear all cache keys with this prefix."""
        return await self.delete_pattern("*")

    async def health_check(self) -> bool:
        """Check Redis connection health."""
        if not self._connected or self._redis is None:
            return False
        try:
            await self._redis.ping()
            return True
        except Exception:
            return False

    @property
    def stats(self) -> CacheStats:
        return self._stats

    @property
    def is_connected(self) -> bool:
        return self._connected


class MultiTierCache:
    """
    Multi-tier cache combining L1 (in-memory) and L2 (Redis).

    Read path: L1 → L2 → miss
    Write path: Write L1 + L2
    Delete path: Delete from both

    Provides sub-millisecond reads for hot data (L1)
    and persistence across restarts (L2).
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        namespace: str = "basira",
        l1_max_size: int = 1000,
        l1_ttl: int = 300,
        l2_ttl: int = 3600,
    ) -> None:
        """
        Args:
            redis_url: Redis connection URL
            namespace: Cache namespace for key isolation
            l1_max_size: L1 cache max entries
            l1_ttl: L1 cache TTL (seconds)
            l2_ttl: L2 cache TTL (seconds)
        """
        self._namespace = namespace
        self._l1 = LRUCache(max_size=l1_max_size, default_ttl=l1_ttl)
        self._l2 = RedisCache(
            redis_url=redis_url,
            prefix=f"{namespace}:cache:",
            default_ttl=l2_ttl,
        )
        self._stats = CacheStats()

        logger.info(
            "cache.multitier_init",
            namespace=namespace,
            l1_max_size=l1_max_size,
            l1_ttl=l1_ttl,
            l2_ttl=l2_ttl,
            l2_connected=self._l2.is_connected,
        )

    def _make_key(self, key: str) -> str:
        """Generate cache key with namespace."""
        return f"{self._namespace}:{key}"

    async def get(self, key: str) -> Any | None:
        """
        Get value from cache.

        Checks L1 first (fast), then L2 (persistent).
        Populates L1 on L2 hit for future fast reads.
        """
        full_key = self._make_key(key)

        # L1 check
        value = self._l1.get(full_key)
        if value is not None:
            self._stats.record_hit()
            return value

        # L2 check
        value = await self._l2.get(full_key)
        if value is not None:
            # Populate L1 for next read
            self._l1.set(full_key, value)
            self._stats.record_hit()
            return value

        self._stats.record_miss()
        return None

    async def set(
        self,
        key: str,
        value: Any,
        l1_ttl: int | None = None,
        l2_ttl: int | None = None,
    ) -> bool:
        """
        Set value in both cache tiers.

        Args:
            key: Cache key
            value: Value to cache
            l1_ttl: L1 TTL override
            l2_ttl: L2 TTL override
        """
        full_key = self._make_key(key)

        # Write L1
        self._l1.set(full_key, value, ttl=l1_ttl)

        # Write L2
        success = await self._l2.set(full_key, value, ttl=l2_ttl)

        self._stats.record_set()
        return success

    async def delete(self, key: str) -> bool:
        """Delete from both cache tiers."""
        full_key = self._make_key(key)

        self._l1.delete(full_key)
        success = await self._l2.delete(full_key)

        self._stats.record_delete()
        return success

    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern from both tiers."""
        full_pattern = self._make_key(pattern)

        # Delete from L1
        keys_to_delete = [k for k in self._l1.get_keys() if self._matches(k, full_pattern)]
        for k in keys_to_delete:
            self._l1.delete(k)

        # Delete from L2
        deleted = await self._l2.delete_pattern(f"{self._namespace}:*{pattern}*")

        return len(keys_to_delete) + deleted

    async def clear(self) -> int:
        """Clear all cache entries."""
        l1_count = self._l1.clear()
        l2_count = await self._l2.clear()
        return l1_count + l2_count

    async def get_or_set(
        self,
        key: str,
        factory: Callable,
        l1_ttl: int | None = None,
        l2_ttl: int | None = None,
    ) -> Any:
        """
        Get from cache, or compute and cache the value.

        Args:
            key: Cache key
            factory: Async callable that generates the value
            l1_ttl: L1 TTL override
            l2_ttl: L2 TTL override

        Returns:
            Cached or freshly computed value.
        """
        value = await self.get(key)
        if value is not None:
            return value

        # Compute value
        if asyncio.iscoroutinefunction(factory):
            value = await factory()
        else:
            value = factory()

        # Cache it
        await self.set(key, value, l1_ttl=l1_ttl, l2_ttl=l2_ttl)
        return value

    async def warm(self, key: str, factory: Callable, l1_ttl: int | None = None) -> None:
        """
        Warm cache by pre-computing and storing a value.

        Useful for expensive queries that are accessed frequently.
        """
        try:
            if asyncio.iscoroutinefunction(factory):
                value = await factory()
            else:
                value = factory()
            await self.set(key, value, l1_ttl=l1_ttl)
            logger.debug("cache.warmed", key=key)
        except Exception as e:
            logger.warning("cache.warm_failed", key=key, error=str(e))

    async def health_check(self) -> dict[str, Any]:
        """Check cache health."""
        l2_healthy = await self._l2.health_check()
        return {
            "status": "healthy" if l2_healthy else "degraded",
            "l1_size": self._l1.size,
            "l1_stats": self._l1.stats.get_stats(),
            "l2_connected": self._l2.is_connected,
            "l2_stats": self._l2.stats.get_stats(),
            "combined_stats": self._stats.get_stats(),
        }

    def get_stats(self) -> dict[str, Any]:
        """Get combined cache statistics."""
        return {
            "l1": self._l1.stats.get_stats(),
            "l2": self._l2.stats.get_stats(),
            "combined": self._stats.get_stats(),
            "l1_size": self._l1.size,
        }

    @staticmethod
    def _matches(key: str, pattern: str) -> bool:
        """Simple pattern matching (supports * wildcard)."""
        import fnmatch
        return fnmatch.fnmatch(key, pattern)
