"""
Unit tests for Phase 2 features.

Tests pricing, supply chain, evaluation, and analytics services.
"""

import pytest
from datetime import date
from unittest.mock import AsyncMock, MagicMock

from src.domain.interfaces.odoo_client import OdooClientInterface
from src.domain.services.pricing_service import PricingService
from src.domain.services.supply_chain_service import SupplyChainService


class MockOdooClient(OdooClientInterface):
    """Mock Odoo client for Phase 2 tests."""

    def __init__(self):
        self.search_read_mock = AsyncMock(return_value=[])

    async def search_read(self, model, domain, fields, limit=100, offset=0, order=None):
        return await self.search_read_mock(model, domain, fields, limit, offset, order)

    async def read(self, model, ids, fields=None):
        return []

    async def fields_get(self, model, attributes=None):
        return {}

    async def execute_kw(self, model, method, args=None, kwargs=None):
        return None

    async def health_check(self):
        return True


@pytest.fixture
def mock_odoo():
    return MockOdooClient()


@pytest.fixture
def pricing_service(mock_odoo):
    return PricingService(mock_odoo)


@pytest.fixture
def supply_chain_service(mock_odoo):
    return SupplyChainService(mock_odoo)


class TestPricingService:
    """Tests for PricingService."""

    @pytest.mark.asyncio
    async def test_get_product_prices_empty(self, pricing_service, mock_odoo):
        """get_product_prices returns empty list when no products."""
        mock_odoo.search_read_mock = AsyncMock(return_value=[])
        prices = await pricing_service.get_product_prices()
        assert prices == []

    @pytest.mark.asyncio
    async def test_get_product_prices_with_data(self, pricing_service, mock_odoo):
        """get_product_prices returns prices with margin calculation."""
        mock_odoo.search_read_mock = AsyncMock(
            return_value=[
                {"id": 1, "name": "Product A", "list_price": 100.0, "standard_price": 60.0},
                {"id": 2, "name": "Product B", "list_price": 50.0, "standard_price": 45.0},
            ]
        )
        prices = await pricing_service.get_product_prices()
        assert len(prices) == 2
        assert prices[0].current_price == 100.0
        assert prices[0].margin_pct == 40.0
        assert prices[1].margin_pct == 10.0


class TestSupplyChainService:
    """Tests for SupplyChainService."""

    @pytest.mark.asyncio
    async def test_get_suppliers_empty(self, supply_chain_service, mock_odoo):
        """get_suppliers returns empty list when no suppliers."""
        mock_odoo.search_read_mock = AsyncMock(return_value=[])
        suppliers = await supply_chain_service.get_suppliers()
        assert suppliers == []

    @pytest.mark.asyncio
    async def test_get_suppliers_with_data(self, supply_chain_service, mock_odoo):
        """get_suppliers returns supplier list."""
        mock_odoo.search_read_mock = AsyncMock(
            return_value=[
                {"id": 1, "name": "Supplier A", "email": "a@test.com", "phone": "123", "city": "Riyadh"},
                {"id": 2, "name": "Supplier B", "email": "b@test.com", "phone": "456", "city": "Jeddah"},
            ]
        )
        suppliers = await supply_chain_service.get_suppliers()
        assert len(suppliers) == 2
        assert suppliers[0].name == "Supplier A"
        assert suppliers[0].city == "Riyadh"

    @pytest.mark.asyncio
    async def test_check_replenishment_needs(self, supply_chain_service, mock_odoo):
        """check_replenishment_needs returns alerts for low stock."""
        mock_odoo.search_read_mock = AsyncMock(
            return_value=[
                {"product_id": 1, "location_id": 1, "quantity": 5, "reserved_quantity": 2},
                {"product_id": 2, "location_id": 1, "quantity": 15, "reserved_quantity": 3},
            ]
        )
        alerts = await supply_chain_service.check_replenishment_needs(threshold=10)
        assert len(alerts) == 1  # Only product with available < 10
        assert alerts[0].urgency == "high"  # available=3 < 5 = high


class TestEvaluationFramework:
    """Tests for evaluation framework."""

    @pytest.mark.asyncio
    async def test_hallucination_detector(self):
        """HallucinationDetector evaluates response correctly."""
        from src.infrastructure.evaluation.eval_harness import HallucinationDetector

        detector = HallucinationDetector(threshold=0.6)

        # Good response with sources
        result = await detector.evaluate(
            query="ما هي مبيعات اليوم؟",
            response="مبيعات اليوم 5000 ريال",
            context="Sales data: 5000 SAR",
            sources=["doc:1"],
        )
        assert result.passed is True
        assert result.score >= 0.6

        # Response with context but no sources — still passes (score 0.8)
        result = await detector.evaluate(
            query="ما هي مبيعات اليوم؟",
            response="مبيعات اليوم 5000 ريال",
            context="Sales data: 5000 SAR",
            sources=[],
        )
        assert result.score == 0.8  # -0.2 for no sources
        assert "no sources cited" in result.details

    @pytest.mark.asyncio
    async def test_answer_quality_scorer(self):
        """AnswerQualityScorer evaluates response quality."""
        from src.infrastructure.evaluation.eval_harness import AnswerQualityScorer

        scorer = AnswerQualityScorer()

        # Good response
        result = await scorer.evaluate(
            query="ما هي مبيعات اليوم؟",
            response="مبيعات اليوم هي 5000 ريال من 10 طلبات",
            agent="analytical",
        )
        assert result.passed is True
        assert result.score >= 0.5

        # Empty response
        result = await scorer.evaluate(
            query="ما هي مبيعات اليوم؟",
            response="",
            agent="analytical",
        )
        assert result.passed is False

    @pytest.mark.asyncio
    async def test_eval_harness(self):
        """EvalHarness runs all evaluations and produces report."""
        from src.infrastructure.evaluation.eval_harness import EvalHarness

        harness = EvalHarness()

        report = await harness.evaluate(
            query="ما هي مبيعات اليوم؟",
            response="مبيعات اليوم 5000 ريال",
            agent="analytical",
            context="Sales data",
            sources=["doc:1"],
        )

        assert report.query == "ما هي مبيعات اليوم؟"
        assert len(report.results) == 2
        assert report.overall_score > 0

        # Check stats
        stats = harness.get_stats()
        assert stats["total"] == 1


class TestAdvancedAnalytics:
    """Tests for advanced analytics."""

    @pytest.mark.asyncio
    async def test_trend_analysis(self, mock_odoo):
        """Trend analysis compares periods correctly."""
        from src.infrastructure.analytics.advanced import AdvancedAnalyticsService

        service = AdvancedAnalyticsService(mock_odoo)

        # Mock sales data for both periods
        mock_odoo.search_read_mock = AsyncMock(
            return_value=[
                {"amount_total": 1000},
                {"amount_total": 2000},
            ]
        )

        trends = await service.analyze_trends(days_back=30)
        assert len(trends) == 3  # sales, orders, avg order value
        assert trends[0].metric_name == "إجمالي المبيعات"

    @pytest.mark.asyncio
    async def test_sales_forecast(self, mock_odoo):
        """Sales forecast uses average from last 30 days."""
        from src.infrastructure.analytics.advanced import AdvancedAnalyticsService

        service = AdvancedAnalyticsService(mock_odoo)

        mock_odoo.search_read_mock = AsyncMock(
            return_value=[
                {"amount_total": 1000},
                {"amount_total": 2000},
            ]
        )

        forecasts = await service.forecast_sales(days_ahead=7)
        assert len(forecasts) == 7
        assert forecasts[0].predicted_sales > 0
        assert forecasts[0].confidence == 0.5


class TestMultiChannelCX:
    """Tests for multi-channel CX handlers."""

    def test_get_channel_config(self):
        """get_channel_config returns config for supported channels."""
        from src.infrastructure.channels.handlers import get_channel_config

        config = get_channel_config("whatsapp")
        assert config is not None
        assert config.channel_name == "WhatsApp Business"

        config = get_channel_config("unknown")
        assert config is None

    def test_format_response_for_channel(self):
        """format_response_for_channel applies channel-specific formatting."""
        from src.infrastructure.channels.handlers import format_response_for_channel

        # WhatsApp truncation
        long_response = "x" * 5000
        formatted = format_response_for_channel(long_response, "whatsapp")
        assert len(formatted) <= 4000

        # Email greeting
        formatted = format_response_for_channel("Test", "email")
        assert formatted.startswith("مرحباً")

    def test_extract_channel_metadata(self):
        """extract_channel_metadata extracts channel-specific fields."""
        from src.infrastructure.channels.handlers import extract_channel_metadata

        metadata = extract_channel_metadata("whatsapp", {"customer_phone": "+966501234567"})
        assert metadata["customer_phone"] == "+966501234567"

        metadata = extract_channel_metadata("email", {"customer_email": "test@test.com"})
        assert metadata["customer_email"] == "test@test.com"
