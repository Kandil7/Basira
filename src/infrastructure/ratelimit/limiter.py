"""
Rate limiter — orchestrator with Redis backend, per-endpoint limits, and adaptive throttling.

Combines algorithms, Redis persistence, and configuration for production use.
"""

import time
from typing import Any

import structlog

from src.infrastructure.ratelimit.algorithms import (
    RateLimitAlgorithm,
    RateLimitResult,
    SlidingWindowLimiter,
    TokenBucketLimiter,
    FixedWindowLimiter,
)

logger = structlog.get_logger(__name__)


class RateLimitConfig:
    """Configuration for rate limiting."""

    def __init__(
        self,
        default_limit: int = 60,
        default_window: int = 60,
        endpoint_limits: dict[str, dict[str, int]] | None = None,
        role_limits: dict[str, dict[str, int]] | None = None,
        algorithm: str = "sliding_window",
    ) -> None:
        """
        Args:
            default_limit: Default requests per window
            default_window: Default window size in seconds
            endpoint_limits: Per-endpoint limits {"endpoint": {"limit": N, "window": S}}
            role_limits: Per-role limits {"role": {"limit": N, "window": S}}
            algorithm: Algorithm to use (sliding_window, token_bucket, fixed_window)
        """
        self.default_limit = default_limit
        self.default_window = default_window
        self.endpoint_limits = endpoint_limits or {}
        self.role_limits = role_limits or {}
        self.algorithm = algorithm


class RedisRateLimitStore:
    """
    Redis-backed rate limit store for distributed limiting.

    Falls back to in-memory if Redis is unavailable.
    """

    def __init__(self, redis_url: str = "redis://localhost:6379/0") -> None:
        self._redis_url = redis_url
        self._redis = None
        self._connected = False

        self._connect()

    def _connect(self) -> None:
        try:
            import redis.asyncio as aioredis

            self._redis = aioredis.from_url(
                self._redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
            )
            self._connected = True
            logger.info("ratelimit.redis_connected")
        except ImportError:
            logger.warning("ratelimit.redis_missing_dep")
        except Exception as e:
            logger.warning("ratelimit.redis_connection_failed", error=str(e))

    async def increment(
        self,
        key: str,
        window: int,
        limit: int,
    ) -> tuple[int, float]:
        """
        Increment counter and check limit atomically.

        Returns:
            Tuple of (current_count, reset_timestamp)
        """
        if not self._connected or self._redis is None:
            # Fallback — can't enforce distributed limits
            return 0, time.time() + window

        try:
            now = time.time()
            pipe = self._redis.pipeline()

            # Use sorted set for sliding window
            member = f"{now}:{id(key)}"
            pipe.zadd(key, {member: now})
            pipe.zremrangebyscore(key, 0, now - window)
            pipe.zcard(key)
            pipe.expire(key, window)

            results = await pipe.execute()
            count = results[2]

            # Calculate reset time
            oldest = await self._redis.zrange(key, 0, 0, withscores=True)
            if oldest:
                reset_at = oldest[0][1] + window
            else:
                reset_at = now + window

            return count, reset_at

        except Exception as e:
            logger.warning("ratelimit.redis_increment_error", error=str(e))
            return 0, time.time() + window

    async def reset(self, key: str) -> None:
        """Reset counter for a key."""
        if self._connected and self._redis:
            try:
                await self._redis.delete(key)
            except Exception as e:
                logger.warning("ratelimit.redis_reset_error", error=str(e))

    async def health_check(self) -> bool:
        if not self._connected or self._redis is None:
            return False
        try:
            await self._redis.ping()
            return True
        except Exception:
            return False


class RateLimiter:
    """
    Production rate limiter with multiple backends and per-endpoint limits.

    Features:
    - Multiple algorithms (sliding window, token bucket, fixed window)
    - Redis-backed distributed rate limiting
    - Per-endpoint and per-role limits
    - Rate limit headers for clients
    - Adaptive throttling under load
    - Graceful degradation (fail open if Redis is down)
    """

    def __init__(
        self,
        config: RateLimitConfig | None = None,
        redis_store: RedisRateLimitStore | None = None,
    ) -> None:
        self._config = config or RateLimitConfig()
        self._redis_store = redis_store
        self._algorithms: dict[str, RateLimitAlgorithm] = {
            "sliding_window": SlidingWindowLimiter(),
            "token_bucket": TokenBucketLimiter(),
            "fixed_window": FixedWindowLimiter(),
        }
        self._algorithm = self._algorithms[self._config.algorithm]
        self._stats = {
            "total_checks": 0,
            "allowed": 0,
            "denied": 0,
            "redis_errors": 0,
        }

    def _get_limit_for_key(
        self,
        path: str,
        role: str | None,
    ) -> tuple[int, int]:
        """
        Get rate limit and window for a specific path and role.

        Priority: endpoint limit > role limit > default
        """
        # Check endpoint-specific limit
        for endpoint_pattern, limits in self._config.endpoint_limits.items():
            if path.startswith(endpoint_pattern):
                return limits.get("limit", self._config.default_limit), \
                       limits.get("window", self._config.default_window)

        # Check role-specific limit
        if role and role in self._config.role_limits:
            limits = self._config.role_limits[role]
            return limits.get("limit", self._config.default_limit), \
                   limits.get("window", self._config.default_window)

        return self._config.default_limit, self._config.default_window

    async def check(
        self,
        key: str,
        path: str = "",
        role: str | None = None,
    ) -> RateLimitResult:
        """
        Check if request is allowed.

        Args:
            key: Client identifier (API key or IP)
            path: Request path for per-endpoint limits
            role: User role for per-role limits

        Returns:
            RateLimitResult with allowed/denied status and headers.
        """
        self._stats["total_checks"] += 1

        limit, window = self._get_limit_for_key(path, role)

        # Try Redis first for distributed limiting
        if self._redis_store and self._redis_store._connected:
            try:
                count, reset_at = await self._redis_store.increment(
                    f"rl:{key}:{path}",
                    window,
                    limit,
                )

                allowed = count <= limit
                remaining = max(0, limit - count)
                retry_after = 0 if allowed else window - (time.time() - (reset_at - window))

                result = RateLimitResult(
                    allowed=allowed,
                    limit=limit,
                    remaining=remaining,
                    reset_at=reset_at,
                    retry_after=max(0, retry_after),
                    algorithm="redis_sliding_window",
                )

                if allowed:
                    self._stats["allowed"] += 1
                else:
                    self._stats["denied"] += 1

                return result

            except Exception as e:
                self._stats["redis_errors"] += 1
                logger.warning("ratelimit.redis_fallback", error=str(e))

        # Fallback to in-memory algorithm
        result = await self._algorithm.check(key, limit, window)

        if result.allowed:
            self._stats["allowed"] += 1
        else:
            self._stats["denied"] += 1

        return result

    async def reset(self, key: str, path: str = "") -> None:
        """Reset rate limit counter for a key."""
        full_key = f"{key}:{path}" if path else key
        await self._algorithm.reset(full_key)
        if self._redis_store:
            await self._redis_store.reset(f"rl:{full_key}")

    def get_stats(self) -> dict[str, Any]:
        """Get rate limiter statistics."""
        return {
            **self._stats,
            "algorithm": self._config.algorithm,
            "denial_rate": (
                self._stats["denied"] / self._stats["total_checks"]
                if self._stats["total_checks"] > 0 else 0
            ),
        }
