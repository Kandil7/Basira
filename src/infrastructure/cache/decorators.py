"""
Cache decorators — easy caching for functions and methods.

Provides @cached, @cache_invalidate, and @cache_warm decorators
for transparent caching without changing function signatures.
"""

import asyncio
import functools
import hashlib
import inspect
from typing import Any, Callable

import structlog

logger = structlog.get_logger(__name__)


def _make_cache_key(
    prefix: str,
    args: tuple,
    kwargs: dict,
    key_func: Callable | None = None,
) -> str:
    """
    Generate a deterministic cache key from function arguments.

    Args:
        prefix: Key prefix (usually function name)
        args: Positional arguments
        kwargs: Keyword arguments
        key_func: Optional custom key generation function

    Returns:
        Deterministic cache key string.
    """
    if key_func:
        return f"{prefix}:{key_func(*args, **kwargs)}"

    # Build key from arguments
    key_parts = [prefix]

    for arg in args:
        if isinstance(arg, (str, int, float, bool)):
            key_parts.append(str(arg))
        elif isinstance(arg, (list, tuple)):
            key_parts.append(str(arg))
        elif isinstance(arg, dict):
            key_parts.append(str(sorted(arg.items())))
        else:
            # For complex objects, use repr
            key_parts.append(repr(arg)[:100])

    for k, v in sorted(kwargs.items()):
        if k in ("self", "cls"):
            continue
        key_parts.append(f"{k}={v}")

    raw = ":".join(key_parts)
    # Hash for consistent length
    return f"{prefix}:{hashlib.md5(raw.encode()).hexdigest()[:16]}"


def cached(
    cache: Any = None,
    prefix: str = "",
    ttl: int | None = None,
    key_func: Callable | None = None,
    condition: Callable | None = None,
) -> Callable:
    """
    Cache function results.

    Usage:
        @cached(cache=my_cache, prefix="analytics", ttl=300)
        async def get_sales(branch_id: str) -> dict:
            ...

    Args:
        cache: MultiTierCache instance
        prefix: Cache key prefix
        ttl: Cache TTL override
        key_func: Custom key generation function
        condition: Optional function to decide if result should be cached

    Returns:
        Decorated function with caching.
    """
    def decorator(func: Callable) -> Callable:
        actual_prefix = prefix or f"func:{func.__module__}.{func.__qualname__}"

        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                if cache is None:
                    return await func(*args, **kwargs)

                cache_key = _make_cache_key(actual_prefix, args, kwargs, key_func)

                # Try cache
                try:
                    cached_value = await cache.get(cache_key)
                    if cached_value is not None:
                        logger.debug("cache.hit", key=cache_key, func=func.__qualname__)
                        return cached_value
                except Exception as e:
                    logger.warning("cache.get_error", key=cache_key, error=str(e))

                # Compute value
                result = await func(*args, **kwargs)

                # Cache result
                if result is not None:
                    should_cache = True
                    if condition:
                        should_cache = condition(result)

                    if should_cache:
                        try:
                            await cache.set(cache_key, result, l2_ttl=ttl)
                            logger.debug("cache.set", key=cache_key, func=func.__qualname__)
                        except Exception as e:
                            logger.warning("cache.set_error", key=cache_key, error=str(e))

                return result

            # Attach invalidation helper
            async def invalidate(*args: Any, **kwargs: Any) -> None:
                if cache is None:
                    return
                cache_key = _make_cache_key(actual_prefix, args, kwargs, key_func)
                await cache.delete(cache_key)
                logger.debug("cache.invalidated", key=cache_key)

            async_wrapper.invalidate = invalidate  # type: ignore
            return async_wrapper

        else:
            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                # For sync functions, just call directly
                # (async cache operations don't apply)
                return func(*args, **kwargs)

            return sync_wrapper

    return decorator


def cache_invalidate(
    cache: Any = None,
    prefix: str = "",
    pattern: str | None = None,
) -> Callable:
    """
    Invalidate cache entries when function is called.

    Usage:
        @cache_invalidate(cache=my_cache, prefix="analytics")
        async def update_sales(data: dict) -> None:
            ...

    Args:
        cache: MultiTierCache instance
        prefix: Cache key prefix to invalidate
        pattern: Pattern to match for bulk invalidation

    Returns:
        Decorated function that invalidates cache after execution.
    """
    def decorator(func: Callable) -> Callable:
        actual_prefix = prefix or f"func:{func.__module__}.{func.__qualname__}"

        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                result = await func(*args, **kwargs)

                if cache is not None:
                    try:
                        if pattern:
                            await cache.delete_pattern(pattern)
                            logger.debug("cache.pattern_invalidated", pattern=pattern)
                        else:
                            # Invalidate by prefix
                            await cache.delete_pattern(f"{actual_prefix}:*")
                            logger.debug("cache.prefix_invalidated", prefix=actual_prefix)
                    except Exception as e:
                        logger.warning("cache.invalidate_error", error=str(e))

                return result

            return async_wrapper

        else:
            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                return func(*args, **kwargs)

            return sync_wrapper

    return decorator


def cache_warm(
    cache: Any = None,
    prefix: str = "",
    ttl: int | None = None,
) -> Callable:
    """
    Warm cache by pre-computing function results.

    Usage:
        @cache_warm(cache=my_cache, prefix="analytics", ttl=3600)
        async def get_daily_report(date: str) -> dict:
            ...

    Args:
        cache: MultiTierCache instance
        prefix: Cache key prefix
        ttl: Cache TTL

    Returns:
        Decorated function that can be called to warm cache.
    """
    def decorator(func: Callable) -> Callable:
        actual_prefix = prefix or f"func:{func.__module__}.{func.__qualname__}"

        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            if cache is None:
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                return func(*args, **kwargs)

            cache_key = _make_cache_key(actual_prefix, args, kwargs)

            # Compute value
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            # Cache it
            if result is not None:
                try:
                    await cache.set(cache_key, result, l2_ttl=ttl)
                    logger.debug("cache.warmed", key=cache_key)
                except Exception as e:
                    logger.warning("cache.warm_error", key=cache_key, error=str(e))

            return result

        return wrapper

    return decorator
