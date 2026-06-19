"""
Connection pooling for Odoo XML-RPC and Qdrant.

Provides managed connection pools for external services to improve
performance and reliability under high concurrency.
"""

import asyncio
import time
from collections import deque
from typing import Any

import structlog

from src.config.settings import Settings

logger = structlog.get_logger(__name__)


class ConnectionPool:
    """
    Generic async connection pool for external services.

    Manages a pool of connections with configurable size and timeout.
    """

    def __init__(
        self,
        name: str,
        max_size: int = 10,
        timeout: int = 30,
    ) -> None:
        self._name = name
        self._max_size = max_size
        self._timeout = timeout
        self._pool: deque = deque()
        self._active = 0
        self._lock = asyncio.Lock()

        logger.info(
            "pool.initialized",
            name=name,
            max_size=max_size,
            timeout=timeout,
        )

    async def acquire(self) -> Any:
        """Acquire a connection from the pool."""
        async with self._lock:
            # Try to get an existing connection
            if self._pool:
                conn = self._pool.popleft()
                logger.debug("pool.acquired_existing", name=self._name)
                return conn

            # Create new connection if under limit
            if self._active < self._max_size:
                self._active += 1
                conn = await self._create_connection()
                logger.debug("pool.created_new", name=self._name, active=self._active)
                return conn

            # Pool is full, wait for release
            logger.warning("pool.full", name=self._name, active=self._active)

        # Wait outside the lock
        return await self._wait_for_connection()

    async def release(self, conn: Any) -> None:
        """Release a connection back to the pool."""
        async with self._lock:
            self._pool.append(conn)
            logger.debug("pool.released", name=self._name, available=len(self._pool))

    async def _create_connection(self) -> Any:
        """Create a new connection. Override in subclass."""
        raise NotImplementedError

    async def _wait_for_connection(self) -> Any:
        """Wait for a connection to become available."""
        start = time.time()
        while time.time() - start < self._timeout:
            async with self._lock:
                if self._pool:
                    conn = self._pool.popleft()
                    return conn
            await asyncio.sleep(0.1)

        raise TimeoutError(f"Connection pool {self._name} timeout after {self._timeout}s")

    @property
    def stats(self) -> dict[str, Any]:
        """Get pool statistics."""
        return {
            "name": self._name,
            "active": self._active,
            "available": len(self._pool),
            "max_size": self._max_size,
        }


class OdooConnectionPool(ConnectionPool):
    """
    Connection pool for Odoo XML-RPC connections.

    Manages XML-RPC ServerProxy instances for Odoo API calls.
    """

    def __init__(self, settings: Settings) -> None:
        super().__init__(
            name="odoo",
            max_size=settings.odoo_pool_size,
            timeout=settings.odoo_pool_timeout,
        )
        self._settings = settings
        self._uid: int | None = None

    async def _create_connection(self) -> Any:
        """Create a new Odoo XML-RPC connection."""
        import xmlrpc.client

        common_url = self._settings.odoo_xmlrpc_url
        object_url = self._settings.odoo_object_url

        common_proxy = xmlrpc.client.ServerProxy(common_url)
        object_proxy = xmlrpc.client.ServerProxy(object_url)

        # Authenticate
        if self._uid is None:
            try:
                self._uid = common_proxy.authenticate(
                    self._settings.odoo_db,
                    self._settings.odoo_username,
                    self._settings.odoo_password,
                    {},
                )
                logger.info("odoo.pool.authenticated", uid=self._uid)
            except Exception as e:
                logger.error("odoo.pool.auth_failed", error=str(e))
                raise

        return {
            "common": common_proxy,
            "object": object_proxy,
            "uid": self._uid,
            "created_at": time.time(),
        }

    async def execute(self, model: str, method: str, args: list | None = None, kwargs: dict | None = None) -> Any:
        """
        Execute an Odoo method using a pooled connection.

        Args:
            model: Odoo model name
            method: Method to execute
            args: Positional arguments
            kwargs: Keyword arguments

        Returns:
            Method result.
        """
        conn = await self.acquire()
        try:
            result = conn["object"].execute_kw(
                self._settings.odoo_db,
                conn["uid"],
                self._settings.odoo_password,
                model,
                method,
                args or [],
                kwargs or {},
            )
            return result
        finally:
            await self.release(conn)


class QdrantConnectionPool(ConnectionPool):
    """
    Connection pool for Qdrant client connections.

    Manages QdrantClient instances for vector store operations.
    """

    def __init__(self, settings: Settings) -> None:
        super().__init__(
            name="qdrant",
            max_size=settings.qdrant_pool_size,
            timeout=30,
        )
        self._settings = settings

    async def _create_connection(self) -> Any:
        """Create a new Qdrant client connection."""
        from qdrant_client import QdrantClient

        client = QdrantClient(
            host=self._settings.qdrant_host,
            port=self._settings.qdrant_port,
        )

        return {
            "client": client,
            "created_at": time.time(),
        }

    async def search(self, **kwargs) -> Any:
        """
        Execute a Qdrant search using a pooled connection.

        Args:
            **kwargs: Search parameters

        Returns:
            Search results.
        """
        conn = await self.acquire()
        try:
            result = conn["client"].search(**kwargs)
            return result
        finally:
            await self.release(conn)

    async def upsert(self, **kwargs) -> Any:
        """
        Execute a Qdrant upsert using a pooled connection.

        Args:
            **kwargs: Upsert parameters

        Returns:
            Upsert result.
        """
        conn = await self.acquire()
        try:
            result = conn["client"].upsert(**kwargs)
            return result
        finally:
            await self.release(conn)


# Global pool instances
_odoo_pool: OdooConnectionPool | None = None
_qdrant_pool: QdrantConnectionPool | None = None


def init_pools(settings: Settings) -> None:
    """Initialize global connection pools."""
    global _odoo_pool, _qdrant_pool

    _odoo_pool = OdooConnectionPool(settings)
    _qdrant_pool = QdrantConnectionPool(settings)

    logger.info("pools.initialized")


def get_odoo_pool() -> OdooConnectionPool | None:
    """Get the global Odoo connection pool."""
    return _odoo_pool


def get_qdrant_pool() -> QdrantConnectionPool | None:
    """Get the global Qdrant connection pool."""
    return _qdrant_pool


def get_pool_stats() -> dict[str, Any]:
    """Get statistics for all connection pools."""
    stats = {}
    if _odoo_pool:
        stats["odoo"] = _odoo_pool.stats
    if _qdrant_pool:
        stats["qdrant"] = _qdrant_pool.stats
    return stats
