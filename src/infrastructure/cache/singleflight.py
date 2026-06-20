"""
Singleflight — stampede protection for cache misses.

Prevents multiple concurrent requests from computing the same value
simultaneously when the cache is empty (cache stampede / thundering herd).
"""

import asyncio
from typing import Any, Callable

import structlog

logger = structlog.get_logger(__name__)


class SingleFlight:
    """
    Singleflight pattern for cache stampede protection.

    When multiple coroutines request the same key simultaneously,
    only one computes the result; others wait for and share the result.

    Usage:
        sf = SingleFlight()

        async def expensive_query(key: str) -> dict:
            return await sf.do(key, _compute_query, key)

        async def _compute_query(key: str) -> dict:
            # Expensive computation
            return await db.query(...)
    """

    def __init__(self) -> None:
        self._in_flight: dict[str, asyncio.Future] = {}
        self._stats = {"total": 0, "shared": 0, "computed": 0}

    async def do(
        self,
        key: str,
        fn: Callable,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """
        Execute function, deduplicating concurrent calls for the same key.

        Args:
            key: Deduplication key
            fn: Async callable to execute
            *args: Positional args for fn
            **kwargs: Keyword args for fn

        Returns:
            Result from fn (shared among concurrent callers).
        """
        self._stats["total"] += 1

        # Check if already in flight
        if key in self._in_flight:
            self._stats["shared"] += 1
            logger.debug("singleflight.share", key=key)
            try:
                return await self._in_flight[key]
            except Exception:
                raise

        # Create future for this key
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._in_flight[key] = future

        try:
            # Execute the function
            if asyncio.iscoroutinefunction(fn):
                result = await fn(*args, **kwargs)
            else:
                result = fn(*args, **kwargs)

            self._stats["computed"] += 1
            logger.debug("singleflight.compute", key=key)

            # Resolve the future
            future.set_result(result)
            return result

        except Exception as e:
            future.set_exception(e)
            raise

        finally:
            # Clean up
            self._in_flight.pop(key, None)

    def get_stats(self) -> dict[str, Any]:
        """Get singleflight statistics."""
        return {
            **self._stats,
            "in_flight_count": len(self._in_flight),
            "shared_rate": (
                self._stats["shared"] / self._stats["total"]
                if self._stats["total"] > 0 else 0
            ),
        }

    def reset(self) -> None:
        """Reset statistics."""
        self._stats = {"total": 0, "shared": 0, "computed": 0}
