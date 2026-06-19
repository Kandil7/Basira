"""
Sales repository — data access layer for sales data.

Wraps the Odoo client with domain-specific query methods for sales analytics.
"""

from datetime import date

from src.domain.interfaces.odoo_client import OdooClientInterface
from src.domain.models.analytics import SalesData


class SalesRepository:
    """Repository for sales data access via Odoo."""

    def __init__(self, odoo_client: OdooClientInterface) -> None:
        self._odoo = odoo_client

    async def get_daily_sales(
        self,
        report_date: date,
        branch_id: str | None = None,
    ) -> list[SalesData]:
        """
        Fetch sales records for a specific date.

        Args:
            report_date: Date to fetch sales for
            branch_id: Optional branch filter

        Returns:
            List of SalesData records.
        """
        domain: list[list] = [
            ["date_order", ">=", str(report_date)],
            ["date_order", "<", str(report_date + __import__("datetime").timedelta(days=1))],
        ]
        if branch_id:
            domain.append(["warehouse_id", "=", int(branch_id)])

        records = await self._odoo.search_read(
            model="sale.order",
            domain=domain,
            fields=[
                "id",
                "name",
                "date_order",
                "warehouse_id",
                "partner_id",
                "amount_total",
                "order_line",
                "state",
            ],
            limit=1000,
        )

        return [
            SalesData(
                order_id=str(r["id"]),
                order_date=report_date,
                branch_id=str(r.get("warehouse_id", "unknown")),
                branch_name="",
                product_id="",
                product_name="",
                quantity=1,
                unit_price=r.get("amount_total", 0),
                total_amount=r.get("amount_total", 0),
            )
            for r in records
        ]

    async def get_sales_range(
        self,
        start_date: date,
        end_date: date,
        branch_id: str | None = None,
    ) -> list[SalesData]:
        """
        Fetch sales records for a date range.

        Args:
            start_date: Range start
            end_date: Range end
            branch_id: Optional branch filter

        Returns:
            List of SalesData records.
        """
        domain: list[list] = [
            ["date_order", ">=", str(start_date)],
            ["date_order", "<=", str(end_date)],
        ]
        if branch_id:
            domain.append(["warehouse_id", "=", int(branch_id)])

        records = await self._odoo.search_read(
            model="sale.order",
            domain=domain,
            fields=[
                "id",
                "name",
                "date_order",
                "warehouse_id",
                "amount_total",
                "state",
            ],
            limit=5000,
        )

        return [
            SalesData(
                order_id=str(r["id"]),
                order_date=r.get("date_order", start_date),
                branch_id=str(r.get("warehouse_id", "unknown")),
                branch_name="",
                product_id="",
                product_name="",
                quantity=1,
                unit_price=r.get("amount_total", 0),
                total_amount=r.get("amount_total", 0),
            )
            for r in records
        ]
