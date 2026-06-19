"""
Integration tests for API endpoints.

Tests FastAPI routes with mocked dependencies.
"""

import pytest
from httpx import AsyncClient, ASGITransport

from src.api.main import create_app


@pytest.fixture
def app():
    """Create test FastAPI app."""
    return create_app()


@pytest.mark.asyncio
async def test_health_endpoint():
    """Health endpoint returns status."""
    from fastapi import FastAPI
    from src.api.routes.health import router

    test_app = FastAPI()
    test_app.include_router(router, prefix="/api/v1")

    async with AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/health")
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_chat_requires_body():
    """Chat endpoint rejects empty body."""
    from fastapi import FastAPI
    from src.api.routes.chat import router

    test_app = FastAPI()
    test_app.include_router(router, prefix="/api/v1")

    async with AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://test"
    ) as client:
        response = await client.post("/api/v1/chat", json={})
        assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_daily_report_requires_date():
    """Daily report endpoint rejects missing date."""
    from fastapi import FastAPI
    from src.api.routes.analytics import router

    test_app = FastAPI()
    test_app.include_router(router, prefix="/api/v1")

    async with AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://test"
    ) as client:
        response = await client.post("/api/v1/reports/daily", json={})
        assert response.status_code == 422  # Validation error
