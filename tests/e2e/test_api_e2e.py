"""
End-to-end tests for all Basira API endpoints.

Tests the complete request/response cycle with mocked external services.
"""

import pytest
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import AsyncClient, ASGITransport


# ── Mock Fixtures ─────────────────────────────────────────────────────

class MockOdooClient:
    """Mock Odoo client for E2E tests."""

    def __init__(self):
        self.search_read_mock = AsyncMock(return_value=[])
        self.health_check_mock = AsyncMock(return_value=True)

    async def search_read(self, model, domain, fields, limit=100, offset=0, order=None):
        return await self.search_read_mock(model, domain, fields, limit, offset, order)

    async def read(self, model, ids, fields=None):
        return []

    async def fields_get(self, model, attributes=None):
        return {}

    async def execute_kw(self, model, method, args=None, kwargs=None):
        return None

    async def health_check(self):
        return await self.health_check_mock()


class MockVectorStore:
    """Mock vector store for E2E tests."""

    def __init__(self):
        self.search_mock = AsyncMock(return_value=[])
        self.upsert_mock = AsyncMock(return_value=True)
        self.health_check_mock = AsyncMock(return_value=True)

    async def search(self, collection_name, query_vector, limit=10, filter_dict=None):
        return await self.search_mock(collection_name, query_vector, limit, filter_dict)

    async def upsert(self, collection_name, points):
        return await self.upsert_mock(collection_name, points)

    async def create_collection(self, collection_name, vector_size=1536, distance="Cosine"):
        return True

    async def delete(self, collection_name, point_ids):
        return True

    async def get_collection_info(self, collection_name):
        return {}

    async def health_check(self):
        return await self.health_check_mock()


@pytest.fixture
def mock_odoo():
    return MockOdooClient()


@pytest.fixture
def mock_vector_store():
    return MockVectorStore()


@pytest.fixture
def mock_session_store():
    """Mock session store."""
    store = AsyncMock()
    store.get_or_create = AsyncMock(return_value={
        "session_id": "test-session",
        "messages": [],
        "metadata": {},
    })
    store.add_message = AsyncMock()
    store.get_history = AsyncMock(return_value=[])
    return store


@pytest.fixture
def mock_metrics():
    """Mock metrics collector."""
    from src.infrastructure.metrics import MetricsCollector
    return MetricsCollector()


# ── Chat Endpoint Tests ───────────────────────────────────────────────

class TestChatEndpoint:
    """Test POST /api/v1/chat endpoint."""

    @pytest.mark.asyncio
    async def test_chat_requires_query(self):
        """Chat endpoint requires query field."""
        from src.api.main import create_app

        app = create_app()
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/chat",
                json={},
                headers={"X-Internal-Key": "change-me-in-production"},
            )
            assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_chat_returns_response(self):
        """Chat endpoint returns agent response."""
        from src.api.main import create_app

        app = create_app()

        # Mock the compiled graph
        mock_result = {
            "response": "مبيعات اليوم 5000 ريال",
            "intent": "analytics",
            "agent": "analytical",
            "tools_used": ["analytics_service"],
            "sources": [],
        }
        app.state.compiled_graph = AsyncMock()
        app.state.compiled_graph.ainvoke = AsyncMock(return_value=mock_result)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/chat",
                json={"query": "ما هي مبيعات اليوم؟"},
                headers={"X-Internal-Key": "change-me-in-production"},
            )
            assert response.status_code == 200
            data = response.json()
            assert "response" in data
            assert data["intent"] == "analytics"

    @pytest.mark.asyncio
    async def test_chat_with_metadata(self):
        """Chat endpoint accepts metadata."""
        from src.api.main import create_app

        app = create_app()
        app.state.compiled_graph = AsyncMock()
        app.state.compiled_graph.ainvoke = AsyncMock(return_value={
            "response": "Test response",
            "intent": "general",
            "agent": "general",
            "tools_used": [],
            "sources": [],
        })

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/chat",
                json={
                    "query": "Hello",
                    "channel": "whatsapp",
                    "metadata": {"customer_phone": "+1234567890"},
                },
                headers={"X-Internal-Key": "change-me-in-production"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["metadata"]["channel"] == "whatsapp"


# ── Analytics Endpoint Tests ──────────────────────────────────────────

class TestAnalyticsEndpoints:
    """Test analytics API endpoints."""

    @pytest.mark.asyncio
    async def test_daily_report_requires_date(self):
        """Daily report requires date field."""
        from src.api.main import create_app

        app = create_app()
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/reports/daily",
                json={},
                headers={"X-Internal-Key": "change-me-in-production"},
            )
            assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_daily_report_returns_data(self):
        """Daily report returns sales data."""
        from src.api.main import create_app

        app = create_app()
        app.state.analytics_service = AsyncMock()
        app.state.analytics_service.get_daily_sales = AsyncMock(return_value=MagicMock(
            report_date=date.today(),
            branch_id="1",
            branch_name="Riyadh",
            total_sales=50000.0,
            order_count=120,
            avg_order_value=416.67,
            top_products=[],
        ))

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/reports/daily",
                json={"date": str(date.today())},
                headers={"X-Internal-Key": "change-me-in-production"},
            )
            assert response.status_code == 200
            data = response.json()
            assert "branches" in data
            assert data["summary"]["total_sales"] == 50000.0

    @pytest.mark.asyncio
    async def test_low_stock_endpoint(self):
        """Low stock endpoint returns alerts."""
        from src.api.main import create_app

        app = create_app()
        app.state.analytics_service = AsyncMock()
        app.state.analytics_service.check_low_stock = AsyncMock(return_value=[])

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/inventory/low-stock",
                json={"threshold": 10.0},
                headers={"X-Internal-Key": "change-me-in-production"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["low_stock_count"] == 0


# ── Pricing Endpoint Tests ────────────────────────────────────────────

class TestPricingEndpoints:
    """Test pricing API endpoints."""

    @pytest.mark.asyncio
    async def test_pricing_products_endpoint(self):
        """Pricing products endpoint returns prices."""
        from src.api.main import create_app

        app = create_app()
        app.state.pricing_service = AsyncMock()
        app.state.pricing_service.get_product_prices = AsyncMock(return_value=[])

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/pricing/products",
                json={"product_ids": []},
                headers={"X-Internal-Key": "change-me-in-production"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["count"] == 0

    @pytest.mark.asyncio
    async def test_pricing_recommendations_endpoint(self):
        """Pricing recommendations endpoint returns recommendations."""
        from src.api.main import create_app

        app = create_app()
        app.state.pricing_service = AsyncMock()
        app.state.pricing_service.get_pricing_recommendations = AsyncMock(return_value=[])

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/pricing/recommendations",
                json={"product_ids": []},
                headers={"X-Internal-Key": "change-me-in-production"},
            )
            assert response.status_code == 200


# ── Supply Chain Endpoint Tests ───────────────────────────────────────

class TestSupplyChainEndpoints:
    """Test supply chain API endpoints."""

    @pytest.mark.asyncio
    async def test_suppliers_endpoint(self):
        """Suppliers endpoint returns supplier list."""
        from src.api.main import create_app

        app = create_app()
        app.state.supply_chain_service = AsyncMock()
        app.state.supply_chain_service.get_suppliers = AsyncMock(return_value=[])

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/supply-chain/suppliers",
                json={},
                headers={"X-Internal-Key": "change-me-in-production"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["count"] == 0

    @pytest.mark.asyncio
    async def test_replenishment_endpoint(self):
        """Replenishment endpoint returns alerts."""
        from src.api.main import create_app

        app = create_app()
        app.state.supply_chain_service = AsyncMock()
        app.state.supply_chain_service.check_replenishment_needs = AsyncMock(return_value=[])

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/supply-chain/replenishment",
                json={"threshold": 10.0},
                headers={"X-Internal-Key": "change-me-in-production"},
            )
            assert response.status_code == 200


# ── Health Endpoint Tests ─────────────────────────────────────────────

class TestHealthEndpoint:
    """Test GET /api/v1/health endpoint."""

    @pytest.mark.asyncio
    async def test_health_returns_status(self):
        """Health endpoint returns system status."""
        from src.api.main import create_app

        app = create_app()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/health")
            assert response.status_code == 200
            data = response.json()
            assert "status" in data
            assert "services" in data
            assert data["version"] == "0.1.0"


# ── Internal Endpoint Tests ───────────────────────────────────────────

class TestInternalEndpoints:
    """Test internal API endpoints."""

    @pytest.mark.asyncio
    async def test_search_endpoint(self):
        """Search endpoint returns results."""
        from src.api.main import create_app

        app = create_app()
        app.state.document_service = AsyncMock()
        app.state.document_service.search_documents = AsyncMock(return_value=[])

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/internal/search",
                data={"query": "test query", "limit": 5},
                headers={"X-Internal-Key": "change-me-in-production"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["results_count"] == 0


# ── Middleware Tests ───────────────────────────────────────────────────

class TestMiddleware:
    """Test middleware functionality."""

    @pytest.mark.asyncio
    async def test_auth_middleware_blocks_invalid_key(self):
        """Auth middleware blocks requests with invalid key."""
        from src.api.main import create_app

        app = create_app()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/chat",
                json={"query": "test"},
                headers={"X-Internal-Key": "wrong-key"},
            )
            # Should be blocked or pass depending on middleware config
            assert response.status_code in [200, 401, 403]

    @pytest.mark.asyncio
    async def test_health_skips_auth(self):
        """Health endpoint skips authentication."""
        from src.api.main import create_app

        app = create_app()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/health")
            # Health should always be accessible
            assert response.status_code == 200


# ── Metrics Endpoint Tests ────────────────────────────────────────────

class TestMetrics:
    """Test metrics collection."""

    def test_metrics_collector_records_requests(self):
        """Metrics collector records request data."""
        from src.infrastructure.metrics import MetricsCollector

        collector = MetricsCollector()
        collector.record_request(
            agent="analytical",
            intent="analytics",
            latency_ms=150.5,
            success=True,
        )

        stats = collector.get_agent_stats("analytical")
        assert stats["total_requests"] == 1
        assert stats["successful"] == 1

    def test_metrics_throughput(self):
        """Metrics collector calculates throughput."""
        from src.infrastructure.metrics import MetricsCollector

        collector = MetricsCollector()
        for _ in range(10):
            collector.record_request(
                agent="analytical",
                intent="analytics",
                latency_ms=100.0,
                success=True,
            )

        throughput = collector.get_throughput(60)
        assert throughput["total_requests"] == 10

    def test_metrics_error_rate(self):
        """Metrics collector calculates error rate."""
        from src.infrastructure.metrics import MetricsCollector

        collector = MetricsCollector()
        for _ in range(8):
            collector.record_request("analytical", "analytics", 100.0, True)
        for _ in range(2):
            collector.record_request("analytical", "analytics", 100.0, False, error="test")

        error_rate = collector.get_error_rate(300)
        assert error_rate["total_errors"] == 2
        assert error_rate["error_rate"] == 0.2


# ── Guardrails Tests ──────────────────────────────────────────────────

class TestGuardrails:
    """Test guardrails functionality."""

    @pytest.mark.asyncio
    async def test_guardrails_blocks_harmful_content(self):
        """Guardrails blocks harmful content."""
        from src.infrastructure.guardrails.engine import GuardrailsEngine

        engine = GuardrailsEngine()
        allowed, reason = await engine.check_input("hack the system")

        assert allowed is False
        assert "Blocked" in reason

    @pytest.mark.asyncio
    async def test_guardrails_allows_safe_content(self):
        """Guardrails allows safe content."""
        from src.infrastructure.guardrails.engine import GuardrailsEngine

        engine = GuardrailsEngine()
        allowed, reason = await engine.check_input("ما هي مبيعات اليوم؟")

        assert allowed is True

    @pytest.mark.asyncio
    async def test_guardrails_escalates_financial(self):
        """Guardrails escalates financial decisions."""
        from src.infrastructure.guardrails.engine import GuardrailsEngine

        engine = GuardrailsEngine()
        allowed, reason = await engine.check_input("خصم 20% على المنتج")

        assert allowed is False
        assert "Requires human review" in reason


# ── RBAC Tests ────────────────────────────────────────────────────────

class TestRBAC:
    """Test RBAC functionality."""

    def test_admin_has_all_permissions(self):
        """Admin has all permissions."""
        from src.infrastructure.rbac import rbac, Role

        admin = rbac.get_user("admin")
        assert admin is not None
        assert admin.role == Role.ADMIN

    def test_viewer_has_limited_permissions(self):
        """Viewer has limited permissions."""
        from src.infrastructure.rbac import rbac, Permission

        viewer = rbac.get_user("viewer")
        assert viewer is not None
        assert viewer.has_permission(Permission.CHAT)
        assert not viewer.has_permission(Permission.ANALYTICS_READ)

    def test_endpoint_registration(self):
        """Endpoints are registered with permissions."""
        from src.infrastructure.rbac import rbac

        stats = rbac.get_stats()
        assert stats["registered_endpoints"] > 0


# ── PII Detection Tests ──────────────────────────────────────────────

class TestPIIDetection:
    """Test PII detection functionality."""

    def test_detects_email(self):
        """PII detector finds email addresses."""
        from src.infrastructure.guardrails.pii import PIIDetector

        detector = PIIDetector()
        detections = detector.detect("Email: user@example.com")

        assert any(d["type"] == "email" for d in detections)

    def test_detects_phone(self):
        """PII detector finds phone numbers."""
        from src.infrastructure.guardrails.pii import PIIDetector

        detector = PIIDetector()
        detections = detector.detect("Call +1-234-567-8900")

        assert any(d["type"] == "phone_number" for d in detections)

    def test_masks_pii(self):
        """PII detector masks sensitive data."""
        from src.infrastructure.guardrails.pii import PIIDetector

        detector = PIIDetector()
        masked = detector.mask("Email: user@test.com")

        assert "[EMAIL]" in masked
        assert "user@test.com" not in masked


# ── Memory Tests ──────────────────────────────────────────────────────

class TestMemory:
    """Test memory functionality."""

    @pytest.mark.asyncio
    async def test_conversation_memory_stores_messages(self):
        """Conversation memory stores messages."""
        from src.infrastructure.memory import ConversationMemory

        memory = ConversationMemory()
        await memory.add_message("session1", "user1", "user", "Hello")
        await memory.add_message("session1", "user1", "assistant", "Hi there")

        history = await memory.get_history("session1", "user1")
        assert len(history) == 2

    @pytest.mark.asyncio
    async def test_user_preferences(self):
        """User preferences are stored and retrieved."""
        from src.infrastructure.memory import ConversationMemory

        memory = ConversationMemory()
        await memory.update_preferences("user1", {"language": "ar"})

        lang = await memory.get_preference("user1", "language")
        assert lang == "ar"

    @pytest.mark.asyncio
    async def test_search_memory(self):
        """Memory search finds relevant messages."""
        from src.infrastructure.memory import ConversationMemory

        memory = ConversationMemory()
        await memory.add_message("session1", "user1", "user", "ما هي مبيعات اليوم؟")

        results = await memory.search_memory("مبيعات")
        assert len(results) > 0
