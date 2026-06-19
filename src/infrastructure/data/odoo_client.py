"""
Odoo XML-RPC client implementation.

Read-only access to Odoo ERP via XML-RPC. Implements the OdooClientInterface
from the domain layer. All operations are async for non-blocking I/O.
"""

import xmlrpc.client
from typing import Any

import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config.settings import Settings
from src.domain.interfaces.odoo_client import OdooClientInterface

logger = structlog.get_logger(__name__)


class OdooClient(OdooClientInterface):
    """
    Read-only Odoo client using XML-RPC.

    This client connects to Odoo via XML-RPC for reading data only.
    No write operations are supported in Phase 1.
    """

    def __init__(self, settings: Settings) -> None:
        self._url = settings.odoo_url
        self._db = settings.odoo_db
        self._username = settings.odoo_username
        self._password = settings.odoo_password
        self._uid: int | None = None
        self._common_proxy: xmlrpc.client.ServerProxy | None = None
        self._object_proxy: xmlrpc.client.ServerProxy | None = None

    def _get_common_proxy(self) -> xmlrpc.client.ServerProxy:
        """Get or create the XML-RPC common proxy."""
        if self._common_proxy is None:
            self._common_proxy = xmlrpc.client.ServerProxy(f"{self._url}/xmlrpc/2/common")
        return self._common_proxy

    def _get_object_proxy(self) -> xmlrpc.client.ServerProxy:
        """Get or create the XML-RPC object proxy."""
        if self._object_proxy is None:
            self._object_proxy = xmlrpc.client.ServerProxy(f"{self._url}/xmlrpc/2/object")
        return self._object_proxy

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _authenticate(self) -> int:
        """
        Authenticate with Odoo and cache the user ID.

        Uses exponential backoff retry on failure.

        Returns:
            Authenticated user ID.
        """
        if self._uid is not None:
            return self._uid

        try:
            common = self._get_common_proxy()
            self._uid = common.authenticate(self._db, self._username, self._password, {})
            if not self._uid:
                raise ConnectionError("Odoo authentication failed — invalid credentials")
            logger.info("odoo.authenticated", uid=self._uid)
            return self._uid
        except Exception as e:
            logger.error("odoo.auth_failed", error=str(e))
            raise

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
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
        Search and read Odoo records via XML-RPC.

        Args:
            model: Odoo model name (e.g., 'sale.order')
            domain: Odoo domain filter
            fields: Fields to read
            limit: Max records
            offset: Pagination offset
            order: Sort order

        Returns:
            List of record dictionaries.
        """
        uid = await self._authenticate()
        obj = self._get_object_proxy()

        kwargs: dict[str, Any] = {
            "fields": fields,
            "limit": limit,
            "offset": offset,
        }
        if order:
            kwargs["order"] = order

        try:
            result = obj.execute_kw(
                self._db,
                uid,
                self._password,
                model,
                "search_read",
                [domain],
                kwargs,
            )
            logger.info(
                "odoo.search_read",
                model=model,
                domain=str(domain)[:200],
                count=len(result),
            )
            return result  # type: ignore[no-any-return]
        except Exception as e:
            logger.error("odoo.search_read_failed", model=model, error=str(e))
            raise

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
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
            ids: Record IDs to read
            fields: Optional fields (None = all)

        Returns:
            List of record dictionaries.
        """
        uid = await self._authenticate()
        obj = self._get_object_proxy()

        kwargs: dict[str, Any] = {}
        if fields:
            kwargs["fields"] = fields

        try:
            result = obj.execute_kw(
                self._db,
                uid,
                self._password,
                model,
                "read",
                [ids],
                kwargs,
            )
            logger.info("odoo.read", model=model, ids_count=len(ids))
            return result  # type: ignore[no-any-return]
        except Exception as e:
            logger.error("odoo.read_failed", model=model, error=str(e))
            raise

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
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
            Field definitions dictionary.
        """
        uid = await self._authenticate()
        obj = self._get_object_proxy()

        kwargs: dict[str, Any] = {}
        if attributes:
            kwargs["attributes"] = attributes

        try:
            result = obj.execute_kw(
                self._db,
                uid,
                self._password,
                model,
                "fields_get",
                [],
                kwargs,
            )
            return result  # type: ignore[no-any-return]
        except Exception as e:
            logger.error("odoo.fields_get_failed", model=model, error=str(e))
            raise

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def execute_kw(
        self,
        model: str,
        method: str,
        args: list[Any] | None = None,
        kwargs: dict[str, Any] | None = None,
    ) -> Any:
        """
        Execute an arbitrary Odoo method via XML-RPC.

        Args:
            model: Odoo model name
            method: Method to execute
            args: Positional arguments
            kwargs: Keyword arguments

        Returns:
            Method result.
        """
        uid = await self._authenticate()
        obj = self._get_object_proxy()

        try:
            result = obj.execute_kw(
                self._db,
                uid,
                self._password,
                model,
                method,
                args or [],
                kwargs or {},
            )
            logger.info("odoo.execute_kw", model=model, method=method)
            return result
        except Exception as e:
            logger.error("odoo.execute_kw_failed", model=model, method=method, error=str(e))
            raise

    async def health_check(self) -> bool:
        """Check if Odoo connection is alive."""
        try:
            common = self._get_common_proxy()
            version = common.version()
            logger.info("odoo.health_check", version=version.get("server_version", "unknown"))
            return True
        except Exception as e:
            logger.error("odoo.health_check_failed", error=str(e))
            return False
