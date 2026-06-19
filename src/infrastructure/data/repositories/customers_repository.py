"""
Customers repository — data access layer for customer data.

Prepared for CX Agent use. Wraps Odoo client for customer/partner queries.
"""

from typing import Any

from src.domain.interfaces.odoo_client import OdooClientInterface
from src.domain.models.customer import BranchInfo, Customer, Order


class CustomerRepository:
    """Repository for customer data access via Odoo."""

    def __init__(self, odoo_client: OdooClientInterface) -> None:
        self._odoo = odoo_client

    async def get_customer(self, customer_id: str) -> Customer | None:
        """
        Get customer details from Odoo.

        Args:
            customer_id: Odoo partner ID

        Returns:
            Customer object if found, None otherwise.
        """
        records = await self._odoo.search_read(
            model="res.partner",
            domain=[["id", "=", int(customer_id)]],
            fields=[
                "id", "name", "email", "phone", "mobile",
                "street", "city", "country_id", "is_company",
            ],
            limit=1,
        )

        if not records:
            return None

        r = records[0]
        return Customer(
            customer_id=str(r["id"]),
            name=r.get("name", ""),
            email=r.get("email"),
            phone=r.get("phone"),
            mobile=r.get("mobile"),
            address=r.get("street"),
            city=r.get("city"),
            is_company=r.get("is_company", False),
        )

    async def get_customer_orders(
        self,
        customer_id: str,
        limit: int = 10,
    ) -> list[Order]:
        """
        Get order history for a customer.

        Args:
            customer_id: Odoo partner ID
            limit: Maximum orders to return

        Returns:
            List of recent orders.
        """
        from datetime import date as date_type

        records = await self._odoo.search_read(
            model="sale.order",
            domain=[["partner_id", "=", int(customer_id)]],
            fields=["id", "name", "date_order", "state", "amount_total"],
            limit=limit,
            order="date_order desc",
        )

        return [
            Order(
                order_id=str(r["id"]),
                order_number=r.get("name", ""),
                customer_id=customer_id,
                customer_name="",
                order_date=r.get("date_order", date_type.today()),
                state=r.get("state", "unknown"),
                total_amount=r.get("amount_total", 0),
            )
            for r in records
        ]

    async def search_customers(
        self,
        query: str,
        limit: int = 20,
    ) -> list[Customer]:
        """
        Search customers by name or email.

        Args:
            query: Search term
            limit: Maximum results

        Returns:
            List of matching customers.
        """
        records = await self._odoo.search_read(
            model="res.partner",
            domain=[["name", "ilike", query]],
            fields=["id", "name", "email", "phone"],
            limit=limit,
        )

        return [
            Customer(
                customer_id=str(r["id"]),
                name=r.get("name", ""),
                email=r.get("email"),
                phone=r.get("phone"),
            )
            for r in records
        ]

    async def get_branch_info(self, branch_id: str) -> BranchInfo | None:
        """
        Get branch details from Odoo warehouse.

        Args:
            branch_id: Warehouse ID

        Returns:
            BranchInfo if found, None otherwise.
        """
        records = await self._odoo.search_read(
            model="stock.warehouse",
            domain=[["id", "=", int(branch_id)]],
            fields=["id", "name", "partner_id"],
            limit=1,
        )

        if not records:
            return None

        r = records[0]
        return BranchInfo(
            branch_id=str(r["id"]),
            branch_name=r.get("name", ""),
        )
