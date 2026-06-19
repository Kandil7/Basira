"""
Domain layer — business logic and interfaces.

This package contains the core business logic with ZERO framework dependencies.
Only Pydantic is used for data models. No FastAPI, Qdrant, or LangGraph imports.
"""

from src.domain.models.analytics import BranchKPI, DailyReport, SalesData
from src.domain.models.customer import Customer, Order, SupportTicket
from src.domain.models.document import DocumentChunk, ReportSummary

__all__ = [
    "BranchKPI",
    "Customer",
    "DailyReport",
    "DocumentChunk",
    "Order",
    "ReportSummary",
    "SalesData",
    "SupportTicket",
]
