"""
Unit tests for configuration settings.
"""

import pytest
import os
from unittest.mock import patch


class TestSettings:
    """Tests for Settings model."""

    def test_default_settings(self):
        """Settings loads with defaults."""
        from src.config.settings import Settings

        with patch.dict(os.environ, {}, clear=False):
            settings = Settings()
            assert settings.app_env == "development"
            assert settings.groq_model == "llama-3.3-70b-versatile"
            assert settings.qdrant_host == "localhost"
            assert settings.qdrant_port == 6333

    def test_qdrant_url_property(self):
        """qdrant_url returns full URL."""
        from src.config.settings import Settings

        settings = Settings(qdrant_host="myhost", qdrant_port=6333)
        assert settings.qdrant_url == "http://myhost:6333"

    def test_odoo_xmlrpc_url(self):
        """odoo_xmlrpc_url returns correct endpoint."""
        from src.config.settings import Settings

        settings = Settings(odoo_url="https://odoo.example.com")
        assert settings.odoo_xmlrpc_url == "https://odoo.example.com/xmlrpc/2/common"

    def test_odoo_object_url(self):
        """odoo_object_url returns correct endpoint."""
        from src.config.settings import Settings

        settings = Settings(odoo_url="https://odoo.example.com")
        assert settings.odoo_object_url == "https://odoo.example.com/xmlrpc/2/object"
