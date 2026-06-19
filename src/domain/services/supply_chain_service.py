"""
Supply chain domain service.

Handles supplier management, procurement, and auto-replenishment.
Pure business logic with no framework dependencies.
"""

from datetime import date, timedelta

from src.domain.interfaces.odoo_client import OdooClientInterface
from src.domain.models.supply_chain import (
    PurchaseOrder,
    ReplenishmentAlert,
    Supplier,
    SupplierPerformance,
)


class SupplyChainService:
    """Business logic for supply chain and procurement operations."""

    def __init__(self, odoo_client: OdooClientInterface) -> None:
        self._odoo = odoo_client

    async def get_suppliers(
        self,
        active_only: bool = True,
    ) -> list[Supplier]:
        """
        Get supplier list from Odoo.

        Args:
            active_only: Only return active suppliers

        Returns:
            List of Supplier records.
        """
        domain: list[list] = [["supplier_rank", ">", 0]]
        if active_only:
            domain.append(["active", "=", True])

        records = await self._odoo.search_read(
            model="res.partner",
            domain=domain,
            fields=[
                "id", "name", "email", "phone", "city", "country_id",
                "supplier_rank",
            ],
            limit=200,
        )

        return [
            Supplier(
                supplier_id=str(r["id"]),
                name=r.get("name", ""),
                email=r.get("email"),
                phone=r.get("phone"),
                city=r.get("city"),
            )
            for r in records
        ]

    async def get_purchase_orders(
        self,
        supplier_id: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int = 50,
    ) -> list[PurchaseOrder]:
        """
        Get purchase orders from Odoo.

        Args:
            supplier_id: Optional supplier filter
            start_date: Optional start date
            end_date: Optional end date
            limit: Maximum records

        Returns:
            List of PurchaseOrder records.
        """
        domain: list[list] = []
        if supplier_id:
            domain.append(["partner_id", "=", int(supplier_id)])
        if start_date:
            domain.append(["date_order", ">=", str(start_date)])
        if end_date:
            domain.append(["date_order", "<=", str(end_date)])

        records = await self._odoo.search_read(
            model="purchase.order",
            domain=domain,
            fields=[
                "id", "name", "partner_id", "date_order", "state",
                "amount_total", "date_planned",
            ],
            limit=limit,
            order="date_order desc",
        )

        return [
            PurchaseOrder(
                order_id=str(r["id"]),
                order_number=r.get("name", ""),
                supplier_id=str(r.get("partner_id", "")),
                supplier_name="",
                order_date=r.get("date_order", date.today()),
                state=r.get("state", "draft"),
                total_amount=r.get("amount_total", 0),
                expected_date=r.get("date_planned"),
            )
            for r in records
        ]

    async def check_replenishment_needs(
        self,
        threshold: float = 10.0,
    ) -> list[ReplenishmentAlert]:
        """
        Check for products that need replenishment.

        Args:
            threshold: Minimum stock level to trigger alert

        Returns:
            List of ReplenishmentAlert for low-stock products.
        """
        # Get current stock levels
        quants = await self._odoo.search_read(
            model="stock.quant",
            domain=[["quantity", "<", threshold]],
            fields=[
                "product_id", "location_id", "quantity",
                "reserved_quantity",
            ],
            limit=500,
        )

        alerts: list[ReplenishmentAlert] = []
        for q in quants:
            product_id = str(q.get("product_id", ""))
            location_id = str(q.get("location_id", ""))
            on_hand = q.get("quantity", 0)
            reserved = q.get("reserved_quantity", 0)
            available = on_hand - reserved

            if available < threshold:
                urgency = "critical" if available <= 0 else "high" if available < 5 else "medium"

                alerts.append(
                    ReplenishmentAlert(
                        product_id=product_id,
                        product_name="Product",
                        branch_id=location_id,
                        branch_name="Branch",
                        current_stock=on_hand,
                        reorder_point=threshold,
                        suggested_order_qty=max(threshold * 2 - available, threshold),
                        estimated_cost=0,
                        urgency=urgency,
                    )
                )

        return alerts

    async def get_supplier_performance(
        self,
        supplier_id: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> SupplierPerformance | None:
        """
        Get supplier performance metrics.

        Args:
            supplier_id: Supplier ID
            start_date: Period start
            end_date: Period end

        Returns:
            SupplierPerformance if found, None otherwise.
        """
        start = start_date or (date.today() - timedelta(days=90))
        end = end_date or date.today()

        orders = await self.get_purchase_orders(supplier_id, start, end)

        if not orders:
            return None

        total_orders = len(orders)
        completed = [o for o in orders if o.state == "done"]
        on_time = len(completed)  # Simplified — would need actual delivery dates
        total_spend = sum(o.total_amount for o in orders)

        return SupplierPerformance(
            supplier_id=supplier_id,
            supplier_name="",
            period=f"{start} to {end}",
            total_orders=total_orders,
            on_time_delivery_pct=(on_time / total_orders * 100) if total_orders > 0 else 0,
            avg_lead_time_days=0,  # Would need delivery date tracking
            total_spend=total_spend,
        )
