"""
Unit tests for domain models.

Validates Pydantic model schemas, validation rules, and serialization.
"""

import pytest
from datetime import date, datetime

from src.domain.models.analytics import (
    BranchKPI,
    DailyReport,
    InventoryItem,
    SalesData,
)
from src.domain.models.customer import Customer, Order
from src.domain.models.document import DocumentChunk, ReportSummary


class TestSalesData:
    """Tests for SalesData model."""

    def test_valid_sales_data(self):
        """SalesData accepts valid input."""
        data = SalesData(
            order_id="12345",
            order_date=date.today(),
            branch_id="BR001",
            branch_name="الرياض",
            product_id="P001",
            product_name="Product A",
            quantity=10,
            unit_price=50.0,
            total_amount=500.0,
        )
        assert data.order_id == "12345"
        assert data.total_amount == 500.0

    def test_negative_quantity_rejected(self):
        """SalesData rejects negative quantity."""
        with pytest.raises(Exception):
            SalesData(
                order_id="12345",
                order_date=date.today(),
                branch_id="BR001",
                branch_name="Test",
                product_id="P001",
                product_name="Product",
                quantity=-1,
                unit_price=50.0,
                total_amount=-50.0,
            )


class TestDailyReport:
    """Tests for DailyReport model."""

    def test_valid_daily_report(self):
        """DailyReport accepts valid input."""
        report = DailyReport(
            report_date=date.today(),
            branch_id="BR001",
            branch_name="الرياض",
            total_sales=45000.0,
            order_count=120,
            avg_order_value=375.0,
        )
        assert report.total_sales == 45000.0
        assert report.order_count == 120

    def test_default_values(self):
        """DailyReport uses correct defaults."""
        report = DailyReport(
            report_date=date.today(),
            branch_id="BR001",
            branch_name="Test",
            total_sales=0,
            order_count=0,
            avg_order_value=0,
        )
        assert report.top_products == []
        assert report.sales_data == []


class TestBranchKPI:
    """Tests for BranchKPI model."""

    def test_valid_kpi(self):
        """BranchKPI accepts valid input."""
        kpi = BranchKPI(
            branch_id="BR001",
            branch_name="الرياض",
            period="monthly",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 31),
            total_revenue=1500000.0,
            total_orders=4200,
            avg_order_value=357.14,
        )
        assert kpi.total_revenue == 1500000.0

    def test_csat_score_validation(self):
        """CSAT score must be between 0 and 5."""
        kpi = BranchKPI(
            branch_id="BR001",
            branch_name="Test",
            period="monthly",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 31),
            total_revenue=0,
            total_orders=0,
            avg_order_value=0,
            customer_satisfaction=4.5,
        )
        assert kpi.customer_satisfaction == 4.5


class TestInventoryItem:
    """Tests for InventoryItem model."""

    def test_valid_inventory(self):
        """InventoryItem accepts valid input."""
        item = InventoryItem(
            product_id="P001",
            product_name="Product A",
            branch_id="BR001",
            branch_name="الرياض",
            quantity_on_hand=100,
            quantity_reserved=20,
            quantity_available=80,
        )
        assert item.quantity_available == 80

    def test_needs_reorder_default(self):
        """needs_reorder defaults to False."""
        item = InventoryItem(
            product_id="P001",
            product_name="Test",
            branch_id="BR001",
            branch_name="Test",
            quantity_on_hand=50,
            quantity_reserved=0,
            quantity_available=50,
        )
        assert item.needs_reorder is False


class TestCustomer:
    """Tests for Customer model."""

    def test_valid_customer(self):
        """Customer accepts valid input."""
        customer = Customer(
            customer_id="C001",
            name="Ahmed Ali",
            email="ahmed@example.com",
            phone="+966501234567",
        )
        assert customer.name == "Ahmed Ali"
        assert customer.country == "Saudi Arabia"


class TestOrder:
    """Tests for Order model."""

    def test_valid_order(self):
        """Order accepts valid input."""
        order = Order(
            order_id="12345",
            order_number="SO00123",
            customer_id="C001",
            customer_name="Ahmed",
            order_date=date.today(),
            state="sale",
            total_amount=500.0,
        )
        assert order.state == "sale"
        assert order.currency == "SAR"


class TestDocumentChunk:
    """Tests for DocumentChunk model."""

    def test_valid_chunk(self):
        """DocumentChunk accepts valid input."""
        chunk = DocumentChunk(
            chunk_id="abc123",
            content="Test content",
            document_id="doc001",
            chunk_index=0,
        )
        assert chunk.content == "Test content"


class TestReportSummary:
    """Tests for ReportSummary model."""

    def test_valid_summary(self):
        """ReportSummary accepts valid input."""
        summary = ReportSummary(
            document_id="doc001",
            filename="report.pdf",
            summary_type="full",
            summary="Test summary",
            chunk_count=10,
        )
        assert summary.chunk_count == 10
        assert summary.language == "ar"
