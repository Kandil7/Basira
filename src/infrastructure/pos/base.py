"""
POS connector — base protocol and adapter for Point of Sale systems.

Defines the universal POS interface that all connectors implement.
Supports WooCommerce POS, Square, and custom POS systems.
"""

from abc import ABC, abstractmethod
from datetime import date, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

import structlog

logger = structlog.get_logger(__name__)


class POSTransactionStatus(Enum):
    """POS transaction status."""
    COMPLETED = "completed"
    PENDING = "pending"
    REFUNDED = "refunded"
    CANCELLED = "cancelled"


class POSConfig(BaseModel):
    """POS connection configuration."""
    pos_type: str = Field(description="POS system type (woocommerce, square, custom)")
    base_url: str = Field(description="POS API base URL")
    api_key: str = Field(description="API key or token")
    store_id: str | None = Field(None, description="Store/location ID")
    timeout: int = Field(30, description="Request timeout in seconds")


class POSTransaction(BaseModel):
    """Standard POS transaction model."""
    transaction_id: str
    pos_type: str
    store_id: str | None = None
    amount: float
    currency: str = "SAR"
    status: POSTransactionStatus
    items: list[dict[str, Any]] = Field(default_factory=list)
    customer_id: str | None = None
    customer_name: str | None = None
    timestamp: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class POSProduct(BaseModel):
    """Standard POS product model."""
    product_id: str
    name: str
    sku: str | None = None
    price: float
    stock_quantity: int = 0
    category: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class POSConnector(ABC):
    """
    Abstract POS connector interface.

    All POS adapters must implement these methods.
    """

    def __init__(self, config: POSConfig) -> None:
        self.config = config
        self._connected = False

    @abstractmethod
    async def connect(self) -> bool:
        """Connect to POS system."""
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from POS system."""
        ...

    @abstractmethod
    async def get_transactions(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int = 100,
    ) -> list[POSTransaction]:
        """Get transactions from POS."""
        ...

    @abstractmethod
    async def get_products(
        self,
        category: str | None = None,
        limit: int = 100,
    ) -> list[POSProduct]:
        """Get products from POS."""
        ...

    @abstractmethod
    async def get_product(self, product_id: str) -> POSProduct | None:
        """Get a single product by ID."""
        ...

    @abstractmethod
    async def get_daily_summary(self, summary_date: date) -> dict[str, Any]:
        """Get daily sales summary from POS."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Check POS connection health."""
        ...

    def is_connected(self) -> bool:
        """Check if connected to POS."""
        return self._connected


class WooCommercePOSConnector(POSConnector):
    """
    WooCommerce POS connector via REST API.

    Connects to WooCommerce stores using the REST API.
    """

    async def connect(self) -> bool:
        """Connect to WooCommerce POS."""
        try:
            import httpx

            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                resp = await client.get(
                    f"{self.config.base_url}/wp-json/wc/v3/system_status",
                    auth=(self.config.api_key, ""),
                )
                if resp.status_code == 200:
                    self._connected = True
                    logger.info("pos.woocommerce.connected", url=self.config.base_url)
                    return True
                else:
                    logger.error("pos.woocommerce.auth_failed", status=resp.status_code)
                    return False
        except Exception as e:
            logger.error("pos.woocommerce.connection_failed", error=str(e))
            return False

    async def disconnect(self) -> None:
        """Disconnect from WooCommerce POS."""
        self._connected = False
        logger.info("pos.woocommerce.disconnected")

    async def get_transactions(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int = 100,
    ) -> list[POSTransaction]:
        """Get transactions from WooCommerce."""
        import httpx

        transactions: list[POSTransaction] = []

        try:
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                params: dict[str, Any] = {"per_page": limit}
                if start_date:
                    params["after"] = f"{start_date.isoformat()}T00:00:00"
                if end_date:
                    params["before"] = f"{end_date.isoformat()}T23:59:59"

                resp = await client.get(
                    f"{self.config.base_url}/wp-json/wc/v3/orders",
                    params=params,
                    auth=(self.config.api_key, ""),
                )

                if resp.status_code == 200:
                    orders = resp.json()
                    for order in orders:
                        status_map = {
                            "completed": POSTransactionStatus.COMPLETED,
                            "processing": POSTransactionStatus.PENDING,
                            "refunded": POSTransactionStatus.REFUNDED,
                            "cancelled": POSTransactionStatus.CANCELLED,
                        }
                        status = status_map.get(
                            order.get("status", ""),
                            POSTransactionStatus.PENDING,
                        )

                        items = [
                            {
                                "name": item.get("name", ""),
                                "quantity": item.get("quantity", 0),
                                "total": float(item.get("total", 0)),
                            }
                            for item in order.get("line_items", [])
                        ]

                        transaction = POSTransaction(
                            transaction_id=str(order.get("id", "")),
                            pos_type="woocommerce",
                            store_id=self.config.store_id,
                            amount=float(order.get("total", 0)),
                            currency=order.get("currency", "SAR"),
                            status=status,
                            items=items,
                            customer_id=str(order.get("customer_id", "")),
                            timestamp=datetime.fromisoformat(
                                order.get("date_created", datetime.now().isoformat())
                            ),
                        )
                        transactions.append(transaction)

        except Exception as e:
            logger.error("pos.woocommerce.get_transactions_failed", error=str(e))

        return transactions

    async def get_products(
        self,
        category: str | None = None,
        limit: int = 100,
    ) -> list[POSProduct]:
        """Get products from WooCommerce."""
        import httpx

        products: list[POSProduct] = []

        try:
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                params: dict[str, Any] = {"per_page": limit}
                if category:
                    params["category"] = category

                resp = await client.get(
                    f"{self.config.base_url}/wp-json/wc/v3/products",
                    params=params,
                    auth=(self.config.api_key, ""),
                )

                if resp.status_code == 200:
                    for p in resp.json():
                        stock = p.get("stock_quantity", 0) or 0
                        product = POSProduct(
                            product_id=str(p.get("id", "")),
                            name=p.get("name", ""),
                            sku=p.get("sku"),
                            price=float(p.get("price", 0)),
                            stock_quantity=stock,
                            category=None,  # WooCommerce doesn't return category in product list
                        )
                        products.append(product)

        except Exception as e:
            logger.error("pos.woocommerce.get_products_failed", error=str(e))

        return products

    async def get_product(self, product_id: str) -> POSProduct | None:
        """Get a single product from WooCommerce."""
        import httpx

        try:
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                resp = await client.get(
                    f"{self.config.base_url}/wp-json/wc/v3/products/{product_id}",
                    auth=(self.config.api_key, ""),
                )

                if resp.status_code == 200:
                    p = resp.json()
                    stock = p.get("stock_quantity", 0) or 0
                    return POSProduct(
                        product_id=str(p.get("id", "")),
                        name=p.get("name", ""),
                        sku=p.get("sku"),
                        price=float(p.get("price", 0)),
                        stock_quantity=stock,
                    )

        except Exception as e:
            logger.error("pos.woocommerce.get_product_failed", error=str(e))

        return None

    async def get_daily_summary(self, summary_date: date) -> dict[str, Any]:
        """Get daily sales summary from WooCommerce."""
        transactions = await self.get_transactions(start_date=summary_date, end_date=summary_date)

        total_sales = sum(t.amount for t in transactions)
        total_transactions = len(transactions)
        completed = sum(1 for t in transactions if t.status == POSTransactionStatus.COMPLETED)

        return {
            "date": summary_date.isoformat(),
            "pos_type": "woocommerce",
            "total_sales": total_sales,
            "total_transactions": total_transactions,
            "completed_transactions": completed,
            "avg_transaction": total_sales / total_transactions if total_transactions > 0 else 0,
        }

    async def health_check(self) -> bool:
        """Check WooCommerce connection health."""
        try:
            import httpx

            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{self.config.base_url}/wp-json/wc/v3/system_status",
                    auth=(self.config.api_key, ""),
                )
                return resp.status_code == 200
        except Exception:
            return False


class SquarePOSConnector(POSConnector):
    """
    Square POS connector via Square API.

    Connects to Square POS using the Square Connect API.
    """

    async def connect(self) -> bool:
        """Connect to Square POS."""
        try:
            import httpx

            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                resp = await client.get(
                    "https://connect.squareup.com/v2/locations",
                    headers={"Authorization": f"Bearer {self.config.api_key}"},
                )
                if resp.status_code == 200:
                    self._connected = True
                    logger.info("pos.square.connected")
                    return True
                else:
                    logger.error("pos.square.auth_failed", status=resp.status_code)
                    return False
        except Exception as e:
            logger.error("pos.square.connection_failed", error=str(e))
            return False

    async def disconnect(self) -> None:
        """Disconnect from Square POS."""
        self._connected = False

    async def get_transactions(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int = 100,
    ) -> list[POSTransaction]:
        """Get transactions from Square (placeholder)."""
        # Square API requires OAuth and more complex setup
        logger.info("pos.square.get_transactions_not_implemented")
        return []

    async def get_products(
        self,
        category: str | None = None,
        limit: int = 100,
    ) -> list[POSProduct]:
        """Get products from Square (placeholder)."""
        return []

    async def get_product(self, product_id: str) -> POSProduct | None:
        """Get a single product from Square (placeholder)."""
        return None

    async def get_daily_summary(self, summary_date: date) -> dict[str, Any]:
        """Get daily summary from Square (placeholder)."""
        return {
            "date": summary_date.isoformat(),
            "pos_type": "square",
            "total_sales": 0,
            "total_transactions": 0,
        }

    async def health_check(self) -> bool:
        """Check Square connection health."""
        return await self.connect()


class POSConnectorFactory:
    """Factory for creating POS connectors."""

    _connectors: dict[str, type[POSConnector]] = {
        "woocommerce": WooCommercePOSConnector,
        "square": SquarePOSConnector,
    }

    @classmethod
    def register(cls, pos_type: str, connector_class: type[POSConnector]) -> None:
        """Register a new POS connector type."""
        cls._connectors[pos_type] = connector_class

    @classmethod
    def create(cls, config: POSConfig) -> POSConnector:
        """Create a POS connector based on config type."""
        connector_class = cls._connectors.get(config.pos_type)
        if not connector_class:
            raise ValueError(
                f"Unsupported POS type: {config.pos_type}. "
                f"Available: {list(cls._connectors.keys())}"
            )
        return connector_class(config)

    @classmethod
    def available_types(cls) -> list[str]:
        """List available POS connector types."""
        return list(cls._connectors.keys())
