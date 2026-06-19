"""
Abstract interface for Odoo ERP client.

All Odoo access goes through this interface. The infrastructure layer
implements the concrete XML-RPC client. Domain services depend only on
this abstract contract.
"""

from abc import ABC, abstractmethod
from typing import Any


class OdooClientInterface(ABC):
    """Abstract Odoo client contract."""

    @abstractmethod
    async def search_read(
        self,
        model: str,
        domain: list[list[Any]],
        fields: list[str],
        limit: int = 100,
        offset: int = 0,
        order: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Search and read Odoo records.

        Args:
            model: Odoo model name (e.g., 'sale.order')
            domain: Odoo search domain filter
            fields: List of fields to read
            limit: Maximum records to return
            offset: Record offset for pagination
            order: Sort order string

        Returns:
            List of record dictionaries.
        """
        ...

    @abstractmethod
    async def read(
        self,
        model: str,
        ids: list[int],
        fields: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Read specific Odoo records by ID.

        Args:
            model: Odoo model name
            ids: List of record IDs to read
            fields: Optional list of fields (None = all fields)

        Returns:
            List of record dictionaries.
        """
        ...

    @abstractmethod
    async def fields_get(
        self,
        model: str,
        attributes: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Get field metadata for an Odoo model.

        Args:
            model: Odoo model name
            attributes: Optional field attributes to retrieve

        Returns:
            Dictionary of field definitions.
        """
        ...

    @abstractmethod
    async def execute_kw(
        self,
        model: str,
        method: str,
        args: list[Any] | None = None,
        kwargs: dict[str, Any] | None = None,
    ) -> Any:
        """
        Execute an Odoo method via XML-RPC.

        Used for computed fields or custom methods not covered by search_read.

        Args:
            model: Odoo model name
            method: Method name to execute
            args: Positional arguments
            kwargs: Keyword arguments

        Returns:
            Method execution result.
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if Odoo connection is alive."""
        ...
