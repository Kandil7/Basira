"""
Production cache infrastructure — multi-tier, decorated, with stampede protection.

Provides:
- Multi-tier cache (L1: in-memory LRU, L2: Redis)
- Cache decorators (@cached, @cache_invalidate)
- Stampede protection (singleflight)
- Cache statistics and monitoring
- Namespace-based key management
- TTL-based expiration
"""

from src.infrastructure.cache.cache import MultiTierCache, LRUCache, RedisCache
from src.infrastructure.cache.decorators import cached, cache_invalidate, cache_warm
from src.infrastructure.cache.singleflight import SingleFlight

__all__ = [
    "MultiTierCache",
    "LRUCache",
    "RedisCache",
    "cached",
    "cache_invalidate",
    "cache_warm",
    "SingleFlight",
]
