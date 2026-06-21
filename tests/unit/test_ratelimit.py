"""
Rate limiter tests — algorithms, middleware, and configuration.
"""

import asyncio
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.infrastructure.ratelimit.algorithms import (
    SlidingWindowLimiter,
    TokenBucketLimiter,
    FixedWindowLimiter,
    RateLimitResult,
)
from src.infrastructure.ratelimit.limiter import (
    RateLimiter,
    RateLimitConfig,
    RedisRateLimitStore,
)


class TestRateLimitResult:
    """Test RateLimitResult dataclass."""

    def test_allowed_result(self):
        result = RateLimitResult(
            allowed=True,
            limit=60,
            remaining=59,
            reset_at=time.time() + 60,
        )
        assert result.allowed is True
        assert result.remaining == 59
        assert "X-RateLimit-Limit" in result.headers
        assert "X-RateLimit-Remaining" in result.headers
        assert "Retry-After" not in result.headers

    def test_denied_result(self):
        result = RateLimitResult(
            allowed=False,
            limit=60,
            remaining=0,
            reset_at=time.time() + 30,
            retry_after=25,
        )
        assert result.allowed is False
        assert result.remaining == 0
        assert "Retry-After" in result.headers

    def test_headers_values(self):
        result = RateLimitResult(
            allowed=True,
            limit=100,
            remaining=95,
            reset_at=1700000000,
        )
        headers = result.headers
        assert headers["X-RateLimit-Limit"] == "100"
        assert headers["X-RateLimit-Remaining"] == "95"
        assert headers["X-RateLimit-Reset"] == "1700000000"


class TestSlidingWindowLimiter:
    """Test sliding window algorithm."""

    def setup_method(self):
        self.limiter = SlidingWindowLimiter()

    def test_name(self):
        assert self.limiter.name == "sliding_window"

    @pytest.mark.asyncio
    async def test_allows_within_limit(self):
        result = await self.limiter.check("key1", limit=5, window=60)
        assert result.allowed is True
        assert result.remaining == 4

    @pytest.mark.asyncio
    async def test_denies_at_limit(self):
        for _ in range(5):
            await self.limiter.check("key1", limit=5, window=60)
        result = await self.limiter.check("key1", limit=5, window=60)
        assert result.allowed is False
        assert result.remaining == 0

    @pytest.mark.asyncio
    async def test_different_keys_independent(self):
        for _ in range(5):
            await self.limiter.check("key1", limit=5, window=60)
        result = await self.limiter.check("key2", limit=5, window=60)
        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_reset(self):
        for _ in range(5):
            await self.limiter.check("key1", limit=5, window=60)
        await self.limiter.reset("key1")
        result = await self.limiter.check("key1", limit=5, window=60)
        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_algorithm_name_in_result(self):
        result = await self.limiter.check("key1", limit=5, window=60)
        assert result.algorithm == "sliding_window"


class TestTokenBucketLimiter:
    """Test token bucket algorithm."""

    def setup_method(self):
        self.limiter = TokenBucketLimiter()

    def test_name(self):
        assert self.limiter.name == "token_bucket"

    @pytest.mark.asyncio
    async def test_allows_burst(self):
        # Should allow full burst
        for _ in range(10):
            result = await self.limiter.check("key1", limit=10, window=60)
            assert result.allowed is True

    @pytest.mark.asyncio
    async def test_denies_after_burst(self):
        for _ in range(10):
            await self.limiter.check("key1", limit=10, window=60)
        result = await self.limiter.check("key1", limit=10, window=60)
        assert result.allowed is False

    @pytest.mark.asyncio
    async def test_refill_over_time(self):
        # Use up all tokens
        for _ in range(5):
            await self.limiter.check("key1", limit=5, window=1)
        # Should be denied
        result = await self.limiter.check("key1", limit=5, window=1)
        assert result.allowed is False
        # Wait for refill
        await asyncio.sleep(0.2)
        result = await self.limiter.check("key1", limit=5, window=1)
        assert result.allowed is True


class TestFixedWindowLimiter:
    """Test fixed window algorithm."""

    def setup_method(self):
        self.limiter = FixedWindowLimiter()

    def test_name(self):
        assert self.limiter.name == "fixed_window"

    @pytest.mark.asyncio
    async def test_allows_within_limit(self):
        result = await self.limiter.check("key1", limit=5, window=60)
        assert result.allowed is True
        assert result.remaining == 4

    @pytest.mark.asyncio
    async def test_denies_at_limit(self):
        for _ in range(5):
            await self.limiter.check("key1", limit=5, window=60)
        result = await self.limiter.check("key1", limit=5, window=60)
        assert result.allowed is False


class TestRateLimitConfig:
    """Test rate limit configuration."""

    def test_default_config(self):
        config = RateLimitConfig()
        assert config.default_limit == 60
        assert config.default_window == 60
        assert config.algorithm == "sliding_window"

    def test_custom_config(self):
        config = RateLimitConfig(
            default_limit=100,
            default_window=30,
            endpoint_limits={
                "/api/v1/chat": {"limit": 20, "window": 60},
            },
            role_limits={
                "admin": {"limit": 200, "window": 60},
            },
            algorithm="token_bucket",
        )
        assert config.default_limit == 100
        assert config.endpoint_limits["/api/v1/chat"]["limit"] == 20
        assert config.role_limits["admin"]["limit"] == 200
        assert config.algorithm == "token_bucket"


class TestRateLimiter:
    """Test RateLimiter orchestrator."""

    def setup_method(self):
        self.config = RateLimitConfig(
            default_limit=5,
            default_window=60,
            endpoint_limits={
                "/api/v1/chat": {"limit": 2, "window": 60},
            },
            role_limits={
                "admin": {"limit": 20, "window": 60},
            },
        )
        self.limiter = RateLimiter(config=self.config)

    @pytest.mark.asyncio
    async def test_default_limit(self):
        for _ in range(5):
            result = await self.limiter.check("key1")
            assert result.allowed is True
        result = await self.limiter.check("key1")
        assert result.allowed is False

    @pytest.mark.asyncio
    async def test_endpoint_limit(self):
        for _ in range(2):
            result = await self.limiter.check("key1", path="/api/v1/chat")
            assert result.allowed is True
        result = await self.limiter.check("key1", path="/api/v1/chat")
        assert result.allowed is False

    @pytest.mark.asyncio
    async def test_role_limit(self):
        for _ in range(20):
            result = await self.limiter.check("key1", role="admin")
            assert result.allowed is True
        result = await self.limiter.check("key1", role="admin")
        assert result.allowed is False

    @pytest.mark.asyncio
    async def test_reset(self):
        for _ in range(5):
            await self.limiter.check("key1")
        await self.limiter.reset("key1")
        result = await self.limiter.check("key1")
        assert result.allowed is True

    def test_stats(self):
        stats = self.limiter.get_stats()
        assert "total_checks" in stats
        assert "allowed" in stats
        assert "denied" in stats
        assert "denial_rate" in stats

    @pytest.mark.asyncio
    async def test_graceful_degradation_no_redis(self):
        """Rate limiter works without Redis."""
        limiter = RateLimiter(config=self.config, redis_store=None)
        result = await limiter.check("key1")
        assert result.allowed is True
        assert result.algorithm == "sliding_window"
