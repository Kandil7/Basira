"""
Cache infrastructure tests — multi-tier cache, decorators, and singleflight.
"""

import asyncio
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.infrastructure.cache.cache import LRUCache, CacheStats, MultiTierCache, RedisCache
from src.infrastructure.cache.decorators import cached, cache_invalidate
from src.infrastructure.cache.singleflight import SingleFlight


class TestCacheStats:
    """Test cache statistics tracking."""

    def setup_method(self):
        self.stats = CacheStats()

    def test_initial_state(self):
        assert self.stats.hits == 0
        assert self.stats.misses == 0
        assert self.stats.hit_rate == 0.0

    def test_record_hit(self):
        self.stats.record_hit()
        self.stats.record_hit()
        assert self.stats.hits == 2

    def test_record_miss(self):
        self.stats.record_miss()
        assert self.stats.misses == 1

    def test_hit_rate(self):
        self.stats.record_hit()
        self.stats.record_hit()
        self.stats.record_miss()
        assert self.stats.hit_rate == pytest.approx(2 / 3)

    def test_hit_rate_empty(self):
        assert self.stats.hit_rate == 0.0

    def test_get_stats(self):
        self.stats.record_hit()
        self.stats.record_set()
        stats = self.stats.get_stats()
        assert stats["hits"] == 1
        assert stats["sets"] == 1
        assert "hit_rate" in stats

    def test_reset(self):
        self.stats.record_hit()
        self.stats.record_miss()
        self.stats.reset()
        assert self.stats.hits == 0
        assert self.stats.misses == 0


class TestLRUCache:
    """Test in-memory LRU cache."""

    def setup_method(self):
        self.cache = LRUCache(max_size=3, default_ttl=60)

    def test_set_and_get(self):
        self.cache.set("key1", "value1")
        assert self.cache.get("key1") == "value1"

    def test_get_missing(self):
        assert self.cache.get("missing") is None

    def test_ttl_expiry(self):
        self.cache.set("key1", "value1", ttl=-1)  # Negative TTL = already expired
        assert self.cache.get("key1") is None

    def test_lru_eviction(self):
        self.cache.set("a", 1)
        self.cache.set("b", 2)
        self.cache.set("c", 3)
        # Add one more — should evict "a" (least recently used)
        self.cache.set("d", 4)
        assert self.cache.get("a") is None
        assert self.cache.get("b") == 2

    def test_lru_access_refreshes(self):
        self.cache.set("a", 1)
        self.cache.set("b", 2)
        self.cache.set("c", 3)
        # Access "a" to refresh it
        self.cache.get("a")
        # Add "d" — should evict "b" now
        self.cache.set("d", 4)
        assert self.cache.get("a") == 1
        assert self.cache.get("b") is None

    def test_delete(self):
        self.cache.set("key1", "value1")
        assert self.cache.delete("key1") is True
        assert self.cache.get("key1") is None

    def test_delete_missing(self):
        assert self.cache.delete("missing") is False

    def test_clear(self):
        self.cache.set("a", 1)
        self.cache.set("b", 2)
        count = self.cache.clear()
        assert count == 2
        assert self.cache.size == 0

    def test_cleanup_expired(self):
        self.cache.set("a", 1, ttl=-1)  # Already expired
        self.cache.set("b", 2, ttl=999)
        removed = self.cache.cleanup_expired()
        assert removed == 1
        assert self.cache.size == 1

    def test_stats(self):
        self.cache.set("a", 1)
        self.cache.get("a")  # hit
        self.cache.get("b")  # miss
        assert self.cache.stats.hits == 1
        assert self.cache.stats.misses == 1

    def test_get_keys(self):
        self.cache.set("a", 1)
        self.cache.set("b", 2)
        keys = self.cache.get_keys()
        assert "a" in keys
        assert "b" in keys


class TestSingleFlight:
    """Test singleflight stampede protection."""

    @pytest.mark.asyncio
    async def test_basic_execution(self):
        sf = SingleFlight()
        call_count = 0

        async def compute():
            nonlocal call_count
            call_count += 1
            return "result"

        result = await sf.do("key1", compute)
        assert result == "result"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_deduplication(self):
        sf = SingleFlight()
        call_count = 0

        async def compute():
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.1)  # Simulate work
            return "result"

        # Launch multiple concurrent calls
        tasks = [sf.do("key1", compute) for _ in range(5)]
        results = await asyncio.gather(*tasks)

        # Should only compute once
        assert call_count == 1
        assert all(r == "result" for r in results)

    @pytest.mark.asyncio
    async def test_different_keys(self):
        sf = SingleFlight()
        call_count = 0

        async def compute(val):
            nonlocal call_count
            call_count += 1
            return val

        results = await asyncio.gather(
            sf.do("a", compute, "a"),
            sf.do("b", compute, "b"),
        )
        assert results == ["a", "b"]
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_exception_propagation(self):
        sf = SingleFlight()

        async def fail():
            raise ValueError("test error")

        with pytest.raises(ValueError, match="test error"):
            await sf.do("key1", fail)

    @pytest.mark.asyncio
    async def test_stats(self):
        sf = SingleFlight()
        call_count = 0

        async def compute():
            nonlocal call_count
            call_count += 1
            return "result"

        # First call computes
        await sf.do("key1", compute)
        # Second call also computes (different key)
        await sf.do("key2", compute)

        stats = sf.get_stats()
        assert stats["total"] == 2
        assert stats["computed"] == 2
        assert stats["shared"] == 0

    def test_reset(self):
        sf = SingleFlight()
        sf._stats["total"] = 10
        sf.reset()
        assert sf._stats["total"] == 0


class TestMultiTierCache:
    """Test MultiTierCache with mocked Redis."""

    def setup_method(self):
        with patch("src.infrastructure.cache.cache.RedisCache") as MockRedis:
            mock_redis = MockRedis.return_value
            mock_redis.is_connected = False
            mock_redis.get = AsyncMock(return_value=None)
            mock_redis.set = AsyncMock(return_value=True)
            mock_redis.delete = AsyncMock(return_value=True)
            mock_redis.clear = AsyncMock(return_value=0)
            mock_redis.health_check = AsyncMock(return_value=False)
            mock_redis.stats = CacheStats()

            self.cache = MultiTierCache(
                redis_url="redis://localhost:6379/0",
                namespace="test",
                l1_max_size=10,
                l1_ttl=60,
                l2_ttl=300,
            )

    @pytest.mark.asyncio
    async def test_set_and_get_l1(self):
        await self.cache.set("key1", "value1")
        # Should be in L1
        result = await self.cache.get("key1")
        assert result == "value1"

    @pytest.mark.asyncio
    async def test_get_missing(self):
        result = await self.cache.get("missing")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete(self):
        await self.cache.set("key1", "value1")
        await self.cache.delete("key1")
        result = await self.cache.get("key1")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_or_set(self):
        call_count = 0

        async def factory():
            nonlocal call_count
            call_count += 1
            return "computed"

        result = await self.cache.get_or_set("key1", factory)
        assert result == "computed"
        assert call_count == 1

        # Second call should hit cache
        result = await self.cache.get_or_set("key1", factory)
        assert result == "computed"
        assert call_count == 1  # Not called again

    @pytest.mark.asyncio
    async def test_health_check(self):
        health = await self.cache.health_check()
        assert health["status"] == "degraded"  # Redis not connected
        assert health["l1_size"] == 0

    @pytest.mark.asyncio
    async def test_stats(self):
        await self.cache.set("a", 1)
        await self.cache.get("a")
        await self.cache.get("missing")
        stats = self.cache.get_stats()
        assert "l1" in stats
        assert "l2" in stats
        assert "combined" in stats
