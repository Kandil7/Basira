"""
Rate limiting algorithms — sliding window, token bucket, fixed window.

Each algorithm implements the same interface for easy swapping.
"""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class RateLimitResult:
    """Result of a rate limit check."""
    allowed: bool
    limit: int
    remaining: int
    reset_at: float  # Unix timestamp when limit resets
    retry_after: float = 0  # Seconds to wait (0 if allowed)
    algorithm: str = ""

    @property
    def headers(self) -> dict[str, str]:
        """HTTP headers for rate limit response."""
        headers = {
            "X-RateLimit-Limit": str(self.limit),
            "X-RateLimit-Remaining": str(max(0, self.remaining)),
            "X-RateLimit-Reset": str(int(self.reset_at)),
        }
        if not self.allowed:
            headers["Retry-After"] = str(int(self.retry_after) + 1)
        return headers


class RateLimitAlgorithm(ABC):
    """Abstract rate limit algorithm interface."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Algorithm name."""
        ...

    @abstractmethod
    async def check(
        self,
        key: str,
        limit: int,
        window: int,
    ) -> RateLimitResult:
        """
        Check if request is allowed.

        Args:
            key: Rate limit key (e.g., user ID, IP)
            limit: Max requests allowed
            window: Window size in seconds

        Returns:
            RateLimitResult with allowed/denied status.
        """
        ...

    @abstractmethod
    async def reset(self, key: str) -> None:
        """Reset counter for a key."""
        ...


class SlidingWindowLimiter(RateLimitAlgorithm):
    """
    Sliding window rate limiter (in-memory).

    More accurate than fixed window — avoids burst at window boundaries.
    Uses a log of timestamps to count requests in the sliding window.
    """

    def __init__(self) -> None:
        self._requests: dict[str, list[float]] = {}

    @property
    def name(self) -> str:
        return "sliding_window"

    async def check(
        self,
        key: str,
        limit: int,
        window: int,
    ) -> RateLimitResult:
        now = time.monotonic()
        window_start = now - window

        # Get existing requests for this key
        requests = self._requests.get(key, [])

        # Prune old requests
        requests = [ts for ts in requests if ts > window_start]

        if len(requests) >= limit:
            # Rate limited
            oldest = requests[0]
            retry_after = window - (now - oldest)
            reset_at = oldest + window

            result = RateLimitResult(
                allowed=False,
                limit=limit,
                remaining=0,
                reset_at=reset_at,
                retry_after=max(0, retry_after),
                algorithm=self.name,
            )
        else:
            # Allowed — record request
            requests.append(now)
            self._requests[key] = requests

            result = RateLimitResult(
                allowed=True,
                limit=limit,
                remaining=limit - len(requests),
                reset_at=now + window,
                algorithm=self.name,
            )

        return result

    async def reset(self, key: str) -> None:
        self._requests.pop(key, None)


class TokenBucketLimiter(RateLimitAlgorithm):
    """
    Token bucket rate limiter (in-memory).

    Allows bursts up to bucket capacity, then refills at a steady rate.
    Good for APIs that need to handle bursty traffic.
    """

    def __init__(self) -> None:
        self._buckets: dict[str, tuple[float, float]] = {}  # key -> (tokens, last_refill)

    @property
    def name(self) -> str:
        return "token_bucket"

    async def check(
        self,
        key: str,
        limit: int,
        window: int,
    ) -> RateLimitResult:
        now = time.monotonic()
        refill_rate = limit / window  # tokens per second

        if key in self._buckets:
            tokens, last_refill = self._buckets[key]
            # Refill tokens
            elapsed = now - last_refill
            tokens = min(limit, tokens + elapsed * refill_rate)
        else:
            tokens = limit
            last_refill = now

        if tokens >= 1:
            # Allowed — consume token
            tokens -= 1
            self._buckets[key] = (tokens, now)

            result = RateLimitResult(
                allowed=True,
                limit=limit,
                remaining=int(tokens),
                reset_at=now + window,
                algorithm=self.name,
            )
        else:
            # Denied — calculate wait time
            wait_time = (1 - tokens) / refill_rate
            self._buckets[key] = (tokens, now)

            result = RateLimitResult(
                allowed=False,
                limit=limit,
                remaining=0,
                reset_at=now + wait_time,
                retry_after=wait_time,
                algorithm=self.name,
            )

        return result

    async def reset(self, key: str) -> None:
        self._buckets.pop(key, None)


class FixedWindowLimiter(RateLimitAlgorithm):
    """
    Fixed window rate limiter (in-memory).

    Simplest algorithm — counts requests in fixed time windows.
    Can allow up to 2x limit at window boundaries (burst problem).
    """

    def __init__(self) -> None:
        self._windows: dict[str, tuple[int, float]] = {}  # key -> (count, window_start)

    @property
    def name(self) -> str:
        return "fixed_window"

    async def check(
        self,
        key: str,
        limit: int,
        window: int,
    ) -> RateLimitResult:
        now = time.monotonic()
        window_start = now - (now % window)  # Align to window boundary

        if key in self._windows:
            count, stored_start = self._windows[key]
            if stored_start < window_start:
                # New window — reset
                count = 0
                stored_start = window_start
        else:
            count = 0
            stored_start = window_start

        if count >= limit:
            reset_at = stored_start + window
            retry_after = reset_at - now

            result = RateLimitResult(
                allowed=False,
                limit=limit,
                remaining=0,
                reset_at=reset_at,
                retry_after=max(0, retry_after),
                algorithm=self.name,
            )
        else:
            count += 1
            self._windows[key] = (count, stored_start)

            result = RateLimitResult(
                allowed=True,
                limit=limit,
                remaining=limit - count,
                reset_at=stored_start + window,
                algorithm=self.name,
            )

        return result

    async def reset(self, key: str) -> None:
        self._windows.pop(key, None)
