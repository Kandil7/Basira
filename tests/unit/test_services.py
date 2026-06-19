"""
Unit tests for domain services.

Tests business logic with mocked infrastructure dependencies.
"""

import pytest
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

from src.domain.interfaces.odoo_client import OdooClientInterface
from src.domain.services.analytics_service import AnalyticsService
from src.domain.services.customer_service import CustomerService
from src.domain.services.document_service import DocumentService


class MockOdooClient(OdooClientInterface):
    """Mock Odoo client for testing."""

    def __init__(self):
        self.search_read_mock = AsyncMock(return_value=[])
        self.read_mock = AsyncMock(return_value=[])
        self.fields_get_mock = AsyncMock(return_value={})
        self.execute_kw_mock = AsyncMock(return_value=None)
        self.health_check_mock = AsyncMock(return_value=True)

    async def search_read(self, model, domain, fields, limit=100, offset=0, order=None):
        return await self.search_read_mock(model, domain, fields, limit, offset, order)

    async def read(self, model, ids, fields=None):
        return await self.read_mock(model, ids, fields)

    async def fields_get(self, model, attributes=None):
        return await self.fields_get_mock(model, attributes)

    async def execute_kw(self, model, method, args=None, kwargs=None):
        return await self.execute_kw_mock(model, method, args, kwargs)

    async def health_check(self):
        return await self.health_check_mock()


class MockVectorStore:
    """Mock vector store for testing."""

    def __init__(self):
        self.upsert_mock = AsyncMock(return_value=True)
        self.search_mock = AsyncMock(return_value=[])
        self.create_collection_mock = AsyncMock(return_value=True)
        self.delete_mock = AsyncMock(return_value=True)
        self.get_collection_info_mock = AsyncMock(return_value={})
        self.health_check_mock = AsyncMock(return_value=True)

    async def upsert(self, collection_name, points):
        return await self.upsert_mock(collection_name, points)

    async def search(self, collection_name, query_vector, limit=10, filter_dict=None):
        return await self.search_mock(collection_name, query_vector, limit, filter_dict)

    async def create_collection(self, collection_name, vector_size=1536, distance="Cosine"):
        return await self.create_collection_mock(collection_name, vector_size, distance)

    async def delete(self, collection_name, point_ids):
        return await self.delete_mock(collection_name, point_ids)

    async def get_collection_info(self, collection_name):
        return await self.get_collection_info_mock(collection_name)

    async def health_check(self):
        return await self.health_check_mock()


@pytest.fixture
def mock_odoo():
    return MockOdooClient()


@pytest.fixture
def mock_vector_store():
    return MockVectorStore()


@pytest.fixture
def analytics_service(mock_odoo):
    return AnalyticsService(mock_odoo)


@pytest.fixture
def customer_service(mock_odoo):
    return CustomerService(mock_odoo)


@pytest.fixture
def document_service(mock_vector_store):
    return DocumentService(mock_vector_store)


class TestAnalyticsService:
    """Tests for AnalyticsService."""

    @pytest.mark.asyncio
    async def test_get_daily_sales_empty(self, analytics_service, mock_odoo):
        """get_daily_sales returns empty report when no orders."""
        mock_odoo.search_read_mock = AsyncMock(return_value=[])
        report = await analytics_service.get_daily_sales(date.today(), "1")
        assert report.order_count == 0
        assert report.total_sales == 0.0

    @pytest.mark.asyncio
    async def test_get_daily_sales_with_orders(self, analytics_service, mock_odoo):
        """get_daily_sales aggregates order data."""
        mock_odoo.search_read_mock = AsyncMock(
            return_value=[
                {"id": 1, "amount_total": 1000, "warehouse_id": 1},
                {"id": 2, "amount_total": 2000, "warehouse_id": 1},
            ]
        )
        report = await analytics_service.get_daily_sales(date.today(), "1")
        assert report.order_count == 2
        assert report.total_sales == 3000.0
        assert report.avg_order_value == 1500.0

    @pytest.mark.asyncio
    async def test_get_branch_kpis(self, analytics_service, mock_odoo):
        """get_branch_kpis returns KPIs for each branch."""
        mock_odoo.search_read_mock = AsyncMock(
            return_value=[
                {"id": 1, "amount_total": 50000, "date_order": "2025-01-15"},
                {"id": 2, "amount_total": 75000, "date_order": "2025-01-15"},
            ]
        )
        kpis = await analytics_service.get_branch_kpis(
            ["1"], date(2025, 1, 1), date(2025, 1, 31)
        )
        assert len(kpis) == 1
        assert kpis[0].total_revenue == 125000.0
        assert kpis[0].total_orders == 2


class TestCustomerService:
    """Tests for CustomerService."""

    @pytest.mark.asyncio
    async def test_get_order_status_not_found(self, customer_service, mock_odoo):
        """get_order_status returns None for unknown order."""
        mock_odoo.search_read_mock = AsyncMock(return_value=[])
        order = await customer_service.get_order_status("99999")
        assert order is None

    @pytest.mark.asyncio
    async def test_get_order_status_found(self, customer_service, mock_odoo):
        """get_order_status returns Order for valid ID."""
        mock_odoo.search_read_mock = AsyncMock(
            return_value=[
                {
                    "id": 12345,
                    "name": "SO00123",
                    "partner_id": 1,
                    "date_order": date.today(),
                    "state": "sale",
                    "amount_total": 500.0,
                    "currency_id": 1,
                    "warehouse_id": 1,
                }
            ]
        )
        order = await customer_service.get_order_status("12345")
        assert order is not None
        assert order.order_number == "SO00123"
        assert order.state == "sale"

    @pytest.mark.asyncio
    async def test_get_customer_history(self, customer_service, mock_odoo):
        """get_customer_history returns list of orders."""
        mock_odoo.search_read_mock = AsyncMock(
            return_value=[
                {"id": 1, "name": "SO001", "date_order": date.today(), "state": "done", "amount_total": 100},
                {"id": 2, "name": "SO002", "date_order": date.today(), "state": "sale", "amount_total": 200},
            ]
        )
        orders = await customer_service.get_customer_history("1")
        assert len(orders) == 2


class TestDocumentService:
    """Tests for DocumentService."""

    def test_chunk_text(self, document_service):
        """_chunk_text splits text into chunks."""
        text = "A" * 2500
        chunks = document_service._chunk_text(text, chunk_size=1000, chunk_overlap=200)
        assert len(chunks) >= 3
        assert all(len(c) <= 1000 for c in chunks)

    def test_chunk_text_short(self, document_service):
        """_chunk_text returns single chunk for short text."""
        chunks = document_service._chunk_text("Hello world", chunk_size=1000)
        assert len(chunks) == 1
        assert chunks[0] == "Hello world"

    @pytest.mark.asyncio
    async def test_ingest_document(self, document_service, mock_vector_store):
        """ingest_document stores chunks in vector store."""
        from src.domain.models.document import IngestRequest

        request = IngestRequest(
            content="Test document content",
            filename="test.txt",
        )
        summary = await document_service.ingest_document(request)
        assert summary.document_id.startswith("doc_")
        assert summary.chunk_count >= 1
        mock_vector_store.upsert_mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_documents(self, document_service, mock_vector_store):
        """search_documents returns matching chunks."""
        mock_vector_store.search_mock = AsyncMock(
            return_value=[
                {
                    "id": "chunk1",
                    "payload": {"content": "Found document", "document_id": "doc1", "chunk_index": 0},
                }
            ]
        )
        results = await document_service.search_documents("test query")
        assert len(results) == 1
        assert results[0].content == "Found document"
