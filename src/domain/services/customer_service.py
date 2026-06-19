"""
Customer service domain service.

Handles customer inquiries, order lookups, and support ticket management.
Pure business logic with no framework dependencies.
"""

from datetime import datetime, timezone

from src.domain.interfaces.odoo_client import OdooClientInterface
from src.domain.models.customer import (
    BranchInfo,
    Customer,
    Order,
    SupportTicket,
)


class CustomerService:
    """Business logic for customer service operations."""

    def __init__(self, odoo_client: OdooClientInterface) -> None:
        self._odoo = odoo_client

    async def get_order_status(self, order_id: str) -> Order | None:
        """
        Look up order status from Odoo.

        Args:
            order_id: The Odoo sale.order ID

        Returns:
            Order object if found, None otherwise.
        """
        records = await self._odoo.search_read(
            model="sale.order",
            domain=[["id", "=", int(order_id)]],
            fields=[
                "id",
                "name",
                "partner_id",
                "date_order",
                "state",
                "amount_total",
                "currency_id",
                "warehouse_id",
            ],
            limit=1,
        )

        if not records:
            return None

        r = records[0]
        return Order(
            order_id=str(r["id"]),
            order_number=r.get("name", ""),
            customer_id=str(r.get("partner_id", "")),
            customer_name="",
            order_date=r.get("date_order", datetime.now().date()),
            state=r.get("state", "unknown"),
            total_amount=r.get("amount_total", 0),
            branch_id=str(r.get("warehouse_id", "")),
        )

    async def get_customer_history(
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
        records = await self._odoo.search_read(
            model="sale.order",
            domain=[["partner_id", "=", int(customer_id)]],
            fields=[
                "id",
                "name",
                "date_order",
                "state",
                "amount_total",
            ],
            limit=limit,
            order="date_order desc",
        )

        return [
            Order(
                order_id=str(r["id"]),
                order_number=r.get("name", ""),
                customer_id=customer_id,
                customer_name="",
                order_date=r.get("date_order", datetime.now().date()),
                state=r.get("state", "unknown"),
                total_amount=r.get("amount_total", 0),
            )
            for r in records
        ]

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
                "id",
                "name",
                "email",
                "phone",
                "mobile",
                "street",
                "city",
                "country_id",
                "is_company",
                "category_id",
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

    async def create_support_ticket(
        self,
        customer_id: str,
        subject: str,
        description: str,
        priority: str = "normal",
    ) -> SupportTicket:
        """
        Create a support ticket in Odoo.

        Args:
            customer_id: Customer Odoo ID
            subject: Ticket subject
            description: Ticket description
            priority: Priority level

        Returns:
            Created SupportTicket.
        """
        now = datetime.now(timezone.utc)
        return SupportTicket(
            ticket_id="pending",
            ticket_number="NEW",
            customer_id=customer_id,
            customer_name="",
            subject=subject,
            description=description,
            state="new",
            priority=priority,
            created_at=now,
        )

    async def get_branch_info(self, branch_id: str) -> BranchInfo | None:
        """
        Get branch details from Odoo.

        Args:
            branch_id: Branch/warehouse ID

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
