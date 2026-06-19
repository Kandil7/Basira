"""
Domain data models for customer service.

Represents customers, orders, and support tickets from the Odoo ERP.
"""

from datetime import date, datetime

from pydantic import BaseModel, Field


class Customer(BaseModel):
    """Customer record from Odoo res.partner."""

    customer_id: str = Field(..., description="Odoo partner ID")
    name: str = Field(..., description="Customer name")
    email: str | None = None
    phone: str | None = None
    mobile: str | None = None
    address: str | None = None
    city: str | None = None
    country: str | None = "Saudi Arabia"
    is_company: bool = False
    tags: list[str] = Field(default_factory=list)
    created_at: datetime | None = None


class Order(BaseModel):
    """Sales order from Odoo sale.order."""

    order_id: str = Field(..., description="Odoo order ID")
    order_number: str = Field(..., description="Human-readable order number")
    customer_id: str
    customer_name: str
    order_date: date
    state: str = Field(description="Order state: draft, sale, done, cancel")
    total_amount: float = Field(ge=0)
    currency: str = "SAR"
    branch_id: str | None = None
    branch_name: str | None = None
    tracking_number: str | None = None
    estimated_delivery: date | None = None
    items: list[dict] = Field(default_factory=list, description="Order line items")


class SupportTicket(BaseModel):
    """Support ticket from Odoo helpdesk.ticket."""

    ticket_id: str
    ticket_number: str
    customer_id: str
    customer_name: str
    subject: str
    description: str
    state: str = Field(description="new, in_progress, done, cancelled")
    priority: str = Field(default="normal", description="low, normal, high, urgent")
    assigned_to: str | None = None
    created_at: datetime
    updated_at: datetime | None = None


class BranchInfo(BaseModel):
    """Branch information from Odoo res.partner (branch type)."""

    branch_id: str
    branch_name: str
    address: str | None = None
    city: str | None = None
    phone: str | None = None
    working_hours: str | None = None
    is_active: bool = True


class CXQuery(BaseModel):
    """Parsed customer service query."""

    raw_query: str
    customer_id: str | None = None
    channel: str = "web"
    language: str = "ar"
    intent: str = Field(description="order_status, policy, branch_info, complaint, general")
