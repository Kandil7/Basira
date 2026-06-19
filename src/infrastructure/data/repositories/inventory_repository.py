"""
Inventory repository — data access layer for stock/inventory data.

Wraps the Odoo client with domain-specific query methods for inventory analytics.
"""

from datetime import date

from src.domain.interfaces.odoo_client import OdooClientInterface
from src.domain.models.analytics import InventoryItem


class InventoryRepository:
    """Repository for inventory data access via Odoo."""

    def __init__(self, odoo_client: OdooClientInterface) -> None:
        self._odoo = odoo_client

    async def get_stock_levels(
        self,
        branch_id: str | None = None,
        product_ids: list[str] | None = None,
    ) -> list[InventoryItem]:
        """
        Fetch current stock levels for products.

        Args:
            branch_id: Optional branch/location filter
            product_ids: Optional product ID filter

        Returns:
            List of InventoryItem with stock levels.
        """
        domain: list[list] = []
        if branch_id:
            domain.append(["location_id", "=", int(branch_id)])
        if product_ids:
            domain.append(["product_id", "in", [int(pid) for pid in product_ids]])

        quants = await self._odoo.search_read(
            model="stock.quant",
            domain=domain,
            fields=[
                "product_id",
                "location_id",
                "quantity",
                "reserved_quantity",
            ],
            limit=5000,
        )

        items: list[InventoryItem] = []
        for q in quants:
            on_hand = q.get("quantity", 0)
            reserved = q.get("reserved_quantity", 0)
            items.append(
                InventoryItem(
                    product_id=str(q.get("product_id", "")),
                    product_name="Product",  # Resolved via product lookup
                    branch_id=str(q.get("location_id", "")),
                    branch_name="Branch",
                    quantity_on_hand=on_hand,
                    quantity_reserved=reserved,
                    quantity_available=on_hand - reserved,
                )
            )

        return items

    async def get_low_stock_items(
        self,
        threshold: float = 10.0,
        branch_id: str | None = None,
    ) -> list[InventoryItem]:
        """
        Get products below reorder threshold.

        Args:
            threshold: Minimum stock level to trigger alert
            branch_id: Optional branch filter

        Returns:
            List of InventoryItem below threshold.
        """
        all_stock = await self.get_stock_levels(branch_id)
        return [item for item in all_stock if item.quantity_available < threshold]

    async def get_product_stock(
        self,
        product_id: str,
        branch_id: str | None = None,
    ) -> InventoryItem | None:
        """
        Get stock level for a specific product.

        Args:
            product_id: Product ID
            branch_id: Optional branch filter

        Returns:
            InventoryItem if found, None otherwise.
        """
        items = await self.get_stock_levels(branch_id, [product_id])
        return items[0] if items else None
