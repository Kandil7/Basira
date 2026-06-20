"""
Health check endpoint.

Provides system health status for monitoring and n8n workflows.
Production: Includes cache, rate limiter, and embedding service health.
"""

import time
from typing import Any

from fastapi import APIRouter, Request
import structlog

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.get("/health")
async def health_check(request: Request) -> dict[str, Any]:
    """
    System health check.

    Returns status of all connected services with response time measurements.
    """
    services: dict[str, Any] = {}
    overall_start = time.time()

    # Check Qdrant
    try:
        qdrant_store = request.app.state.qdrant_store
        start = time.time()
        qdrant_health = await qdrant_store.health_check()
        elapsed_ms = round((time.time() - start) * 1000, 1)
        services["qdrant"] = {
            "status": "connected" if qdrant_health.get("status") == "healthy" else "disconnected",
            "response_time_ms": elapsed_ms,
            "collections": qdrant_health.get("collections_count", 0),
        }
    except Exception as e:
        services["qdrant"] = {"status": "error", "error": str(e)}

    # Check Odoo
    try:
        odoo_client = request.app.state.odoo_client
        start = time.time()
        odoo_ok = await odoo_client.health_check()
        elapsed_ms = round((time.time() - start) * 1000, 1)
        services["odoo"] = {
            "status": "connected" if odoo_ok else "disconnected",
            "response_time_ms": elapsed_ms,
        }
    except Exception as e:
        services["odoo"] = {"status": "error", "error": str(e)}

    # Check LLM
    try:
        settings = request.app.state.settings
        has_key = bool(settings.groq_api_key and settings.groq_api_key != "change-me")
        services["llm"] = {
            "status": "available" if has_key else "no_api_key",
            "model": settings.groq_model,
        }
    except Exception as e:
        services["llm"] = {"status": "error", "error": str(e)}

    # Check Embeddings
    try:
        embedding_service = request.app.state.embedding_service
        start = time.time()
        emb_health = await embedding_service.health_check()
        elapsed_ms = round((time.time() - start) * 1000, 1)
        services["embeddings"] = {
            "status": emb_health.get("status", "unknown"),
            "provider": emb_health.get("provider", "unknown"),
            "dimension": emb_health.get("dimension", 0),
            "response_time_ms": elapsed_ms,
        }
    except Exception as e:
        services["embeddings"] = {"status": "error", "error": str(e)}

    # Check Cache
    try:
        cache = request.app.state.cache
        start = time.time()
        cache_health = await cache.health_check()
        elapsed_ms = round((time.time() - start) * 1000, 1)
        services["cache"] = {
            "status": cache_health.get("status", "unknown"),
            "l1_size": cache_health.get("l1_size", 0),
            "l2_connected": cache_health.get("l2_connected", False),
            "response_time_ms": elapsed_ms,
        }
    except Exception as e:
        services["cache"] = {"status": "error", "error": str(e)}

    # Check Rate Limiter
    try:
        rate_limiter = request.app.state.rate_limiter
        rl_stats = rate_limiter.get_stats()
        services["rate_limiter"] = {
            "status": "active",
            "algorithm": rl_stats.get("algorithm", "unknown"),
            "total_checks": rl_stats.get("total_checks", 0),
            "denial_rate": rl_stats.get("denial_rate", 0),
        }
    except Exception as e:
        services["rate_limiter"] = {"status": "error", "error": str(e)}

    # Check Redis
    try:
        redis_client = request.app.state.redis_client
        if redis_client:
            start = time.time()
            await redis_client.ping()
            elapsed_ms = round((time.time() - start) * 1000, 1)
            services["redis"] = {"status": "connected", "response_time_ms": elapsed_ms}
        else:
            services["redis"] = {"status": "not_configured"}
    except Exception as e:
        services["redis"] = {"status": "error", "error": str(e)}

    total_ms = round((time.time() - overall_start) * 1000, 1)
    healthy_count = sum(
        1 for s in services.values()
        if isinstance(s, dict) and s.get("status") in ("connected", "available", "active", "healthy")
    )

    return {
        "status": "healthy" if healthy_count == len(services) else "degraded",
        "services": services,
        "healthy_count": healthy_count,
        "total_count": len(services),
        "response_time_ms": total_ms,
        "version": "1.0.0",
    }
