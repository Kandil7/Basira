"""
Tests for the POS connector module.
"""

import pytest
from datetime import date, datetime

from src.infrastructure.pos.base import (
    POSConfig,
    POSConnector,
    POSConnectorFactory,
    POSTransaction,
    POSTransactionStatus,
    POSProduct,
    WooCommercePOSConnector,
)


class TestPOSConfig:
    """Test POS configuration."""

    def test_create_config(self):
        """Test creating POS config."""
        config = POSConfig(
            pos_type="woocommerce",
            base_url="https://example.com",
            api_key="test_key",
        )
        assert config.pos_type == "woocommerce"
        assert config.base_url == "https://example.com"
        assert config.api_key == "test_key"
        assert config.timeout == 30

    def test_config_with_store_id(self):
        """Test config with store ID."""
        config = POSConfig(
            pos_type="square",
            base_url="https://connect.squareup.com",
            api_key="test_key",
            store_id="store_123",
        )
        assert config.store_id == "store_123"


class TestPOSTransaction:
    """Test POSTransaction model."""

    def test_create_transaction(self):
        """Test creating a transaction."""
        tx = POSTransaction(
            transaction_id="TX001",
            pos_type="woocommerce",
            amount=150.0,
            currency="SAR",
            status=POSTransactionStatus.COMPLETED,
            timestamp=datetime.now(),
        )
        assert tx.transaction_id == "TX001"
        assert tx.amount == 150.0
        assert tx.status == POSTransactionStatus.COMPLETED

    def test_transaction_status_values(self):
        """Test transaction status enum values."""
        assert POSTransactionStatus.COMPLETED.value == "completed"
        assert POSTransactionStatus.PENDING.value == "pending"
        assert POSTransactionStatus.REFUNDED.value == "refunded"
        assert POSTransactionStatus.CANCELLED.value == "cancelled"


class TestPOSProduct:
    """Test POSProduct model."""

    def test_create_product(self):
        """Test creating a product."""
        product = POSProduct(
            product_id="P001",
            name="حليب طازج",
            sku="MILK-001",
            price=5.5,
            stock_quantity=100,
        )
        assert product.product_id == "P001"
        assert product.name == "حليب طازج"
        assert product.price == 5.5
        assert product.stock_quantity == 100


class TestPOSConnectorFactory:
    """Test POS connector factory."""

    def test_available_types(self):
        """Test listing available POS types."""
        types = POSConnectorFactory.available_types()
        assert "woocommerce" in types
        assert "square" in types

    def test_create_woocommerce_connector(self):
        """Test creating WooCommerce connector."""
        config = POSConfig(
            pos_type="woocommerce",
            base_url="https://example.com",
            api_key="test_key",
        )
        connector = POSConnectorFactory.create(config)
        assert isinstance(connector, WooCommercePOSConnector)

    def test_create_unknown_connector(self):
        """Test creating unknown connector type."""
        config = POSConfig(
            pos_type="unknown_pos",
            base_url="https://example.com",
            api_key="test_key",
        )
        with pytest.raises(ValueError, match="Unsupported POS type"):
            POSConnectorFactory.create(config)


class TestWooCommercePOSConnector:
    """Test WooCommerce POS connector methods."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = POSConfig(
            pos_type="woocommerce",
            base_url="https://example.com",
            api_key="test_key",
        )
        self.connector = WooCommercePOSConnector(self.config)

    def test_initial_state(self):
        """Test initial connector state."""
        assert self.connector.is_connected() is False
        assert self.connector.config.pos_type == "woocommerce"

    @pytest.mark.asyncio
    async def test_disconnect(self):
        """Test disconnect."""
        self.connector._connected = True
        await self.connector.disconnect()
        assert self.connector.is_connected() is False
