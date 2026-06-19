"""
Analytics domain service.

Orchestrates data retrieval from Odoo repositories and computes
analytics insights. No framework dependencies — pure business logic.
"""

from datetime import date, timedelta

from src.domain.interfaces.odoo_client import OdooClientInterface
from src.domain.models.analytics import (
    BranchKPI,
    DailyReport,
    InventoryItem,
    SalesData,
)


class AnalyticsService:
    """Business logic for sales, inventory, and branch analytics."""

    def __init__(self, odoo_client: OdooClientInterface) -> None:
        self._odoo = odoo_client

    async def get_daily_sales(
        self,
        report_date: date,
        branch_id: str | None = None,
    ) -> DailyReport:
        """
        Generate a daily sales report for a branch.

        Args:
            report_date: The date to report on
            branch_id: Optional branch filter

        Returns:
            Aggregated DailyReport.
        """
        domain: list[list] = [["date_order", ">=", str(report_date)]]
        if branch_id:
            domain.append(["warehouse_id", "=", int(branch_id)])

        raw_orders = await self._odoo.search_read(
            model="sale.order",
            domain=domain,
            fields=[
                "id",
                "date_order",
                "warehouse_id",
                "partner_id",
                "order_line",
                "amount_total",
                "state",
            ],
            limit=500,
        )

        sales_records: list[SalesData] = []
        total_sales = 0.0

        for order in raw_orders:
            sales_records.append(
                SalesData(
                    order_id=str(order["id"]),
                    order_date=report_date,
                    branch_id=str(order.get("warehouse_id", "unknown")),
                    branch_name="Branch",  # Resolved via warehouse lookup
                    product_id="",
                    product_name="",
                    quantity=1,
                    unit_price=order.get("amount_total", 0),
                    total_amount=order.get("amount_total", 0),
                )
            )
            total_sales += order.get("amount_total", 0)

        order_count = len(raw_orders)
        avg_order = total_sales / order_count if order_count > 0 else 0.0

        return DailyReport(
            report_date=report_date,
            branch_id=branch_id or "all",
            branch_name="All Branches" if not branch_id else f"Branch {branch_id}",
            total_sales=total_sales,
            order_count=order_count,
            avg_order_value=avg_order,
            top_products=[],
            sales_data=sales_records,
        )

    async def get_branch_kpis(
        self,
        branch_ids: list[str],
        start_date: date,
        end_date: date,
    ) -> list[BranchKPI]:
        """
        Compute KPIs for specified branches over a date range.

        Args:
            branch_ids: List of branch IDs to analyze
            start_date: Period start date
            end_date: Period end date

        Returns:
            List of BranchKPI for each branch.
        """
        kpis: list[BranchKPI] = []

        for branch_id in branch_ids:
            domain: list[list] = [
                ["date_order", ">=", str(start_date)],
                ["date_order", "<=", str(end_date)],
                ["warehouse_id", "=", int(branch_id)],
            ]

            orders = await self._odoo.search_read(
                model="sale.order",
                domain=domain,
                fields=["id", "amount_total", "date_order", "state"],
                limit=1000,
            )

            total_revenue = sum(o.get("amount_total", 0) for o in orders)
            total_orders = len(orders)
            avg_order = total_revenue / total_orders if total_orders > 0 else 0.0

            kpis.append(
                BranchKPI(
                    branch_id=branch_id,
                    branch_name=f"Branch {branch_id}",
                    period="custom",
                    start_date=start_date,
                    end_date=end_date,
                    total_revenue=total_revenue,
                    total_orders=total_orders,
                    avg_order_value=avg_order,
                )
            )

        return kpis

    async def get_inventory_status(
        self,
        branch_id: str | None = None,
    ) -> list[InventoryItem]:
        """
        Get current inventory status.

        Args:
            branch_id: Optional branch filter

        Returns:
            List of InventoryItem with stock levels.
        """
        domain: list[list] = []
        if branch_id:
            domain.append(["location_id", "=", int(branch_id)])

        quants = await self._odoo.search_read(
            model="stock.quant",
            domain=domain,
            fields=[
                "product_id",
                "location_id",
                "quantity",
                "reserved_quantity",
            ],
            limit=1000,
        )

        items: list[InventoryItem] = []
        for q in quants:
            on_hand = q.get("quantity", 0)
            reserved = q.get("reserved_quantity", 0)
            items.append(
                InventoryItem(
                    product_id=str(q.get("product_id", "")),
                    product_name="Product",
                    branch_id=str(q.get("location_id", "")),
                    branch_name="Branch",
                    quantity_on_hand=on_hand,
                    quantity_reserved=reserved,
                    quantity_available=on_hand - reserved,
                )
            )

        return items

    async def check_low_stock(self, threshold: float = 10.0) -> list[InventoryItem]:
        """
        Check for products below reorder threshold.

        Args:
            threshold: Minimum stock level to trigger alert

        Returns:
            List of InventoryItem below threshold.
        """
        all_inventory = await self.get_inventory_status()
        return [item for item in all_inventory if item.quantity_available < threshold]
