"""
Tests for the export engine module.
"""

import io
from unittest.mock import MagicMock

import pytest

from src.infrastructure.export.engine import ExportEngine, ExportFormat


class TestExportEngine:
    """Test ExportEngine functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.engine = ExportEngine()
        self.sample_data = {
            "التاريخ": "2025-01-15",
            "الفرع": "الرياض",
            "إجمالي المبيعات": "45,000.00 ريال",
            "عدد الطلبات": 120,
        }

    def test_export_json(self):
        """Test JSON export."""
        buffer = self.engine.export(self.sample_data, ExportFormat.JSON, "Test Report")

        assert isinstance(buffer, io.BytesIO)
        content = buffer.read().decode("utf-8")
        assert "الرياض" in content
        assert "45,000.00" in content

    def test_export_csv(self):
        """Test CSV export."""
        buffer = self.engine.export(self.sample_data, ExportFormat.CSV)

        assert isinstance(buffer, io.BytesIO)
        content = buffer.read().decode("utf-8-sig")
        assert "الرياض" in content

    def test_export_pdf_fallback(self):
        """Test PDF export with fallback (no reportlab)."""
        buffer = self.engine.export(self.sample_data, ExportFormat.PDF, "Test")

        assert isinstance(buffer, io.BytesIO)
        assert buffer.getbuffer().nbytes > 0

    def test_export_excel(self):
        """Test Excel export."""
        buffer = self.engine.export(self.sample_data, ExportFormat.EXCEL, "Test")

        assert isinstance(buffer, io.BytesIO)
        assert buffer.getbuffer().nbytes > 0

    def test_content_type_json(self):
        """Test content type for JSON."""
        ct = self.engine.get_export_content_type(ExportFormat.JSON)
        assert "json" in ct

    def test_content_type_pdf(self):
        """Test content type for PDF."""
        ct = self.engine.get_export_content_type(ExportFormat.PDF)
        assert "pdf" in ct

    def test_content_type_excel(self):
        """Test content type for Excel."""
        ct = self.engine.get_export_content_type(ExportFormat.EXCEL)
        assert "spreadsheet" in ct

    def test_extension_json(self):
        """Test file extension for JSON."""
        ext = self.engine.get_export_extension(ExportFormat.JSON)
        assert ext == ".json"

    def test_extension_pdf(self):
        """Test file extension for PDF."""
        ext = self.engine.get_export_extension(ExportFormat.PDF)
        assert ext == ".pdf"

    def test_extension_excel(self):
        """Test file extension for Excel."""
        ext = self.engine.get_export_extension(ExportFormat.EXCEL)
        assert ext == ".xlsx"

    def test_export_with_nested_data(self):
        """Test export with nested dictionary data."""
        data = {
            "المبيعات": {"الرياض": "45,000", "جدة": "35,000"},
            "الطلبات": ["طلب 1", "طلب 2", "طلب 3"],
        }

        buffer = self.engine.export(data, ExportFormat.JSON)
        assert buffer.getbuffer().nbytes > 0

    def test_export_with_list_data(self):
        """Test export with list data."""
        data = {
            "المنتجات": ["حليب", "خبز", "زبادي"],
            "المخزون": [100, 200, 150],
        }

        buffer = self.engine.export(data, ExportFormat.CSV)
        assert buffer.getbuffer().nbytes > 0
