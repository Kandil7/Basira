"""
FastAPI application factory.

Creates and configures the FastAPI app with all routes, middleware,
and dependency injection.

Phase 3: Added Redis session store, PostgreSQL audit log, and connection pooling.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.agents.builder import build_graph
from src.api.middleware.auth import AuthMiddleware
from src.api.middleware.rate_limit import RateLimitMiddleware
from src.config.settings import Settings, get_settings
from src.infrastructure.data.odoo_client import OdooClient
from src.infrastructure.logging.config import setup_logging
from src.infrastructure.rag.retriever import Retriever
from src.infrastructure.rag.vectorstore import QdrantVectorStore
from src.infrastructure.rag.embeddings import EmbeddingService
from src.infrastructure.session.redis_store import RedisSessionStore
from src.infrastructure.session.session_store import SessionStore
from src.infrastructure.database.audit import AuditLogService
from src.infrastructure.database.models import init_database, create_tables, close_database
from src.infrastructure.pooling import init_pools, get_pool_stats
from src.domain.services.analytics_service import AnalyticsService
from src.domain.services.customer_service import CustomerService
from src.domain.services.document_service import DocumentService
from src.domain.services.pricing_service import PricingService
from src.domain.services.supply_chain_service import SupplyChainService

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan — startup and shutdown hooks.

    Initializes infrastructure clients and builds the agent graph
    via the builder factory.
    """
    settings = get_settings()

    setup_logging(settings.app_log_level)
    logger.info("app.starting", env=settings.app_env)

    # ── Infrastructure ───────────────────────────────────────────────
    odoo_client = OdooClient(settings)
    qdrant_store = QdrantVectorStore(settings)
    embedding_service = EmbeddingService(settings)
    retriever = Retriever(qdrant_store, settings, embedding_service)

    # Session store (Redis with in-memory fallback)
    try:
        session_store = RedisSessionStore(settings)
        logger.info("session_store.redis")
    except Exception as e:
        logger.warning("session_store.fallback", error=str(e))
        session_store = SessionStore()

    # Database (PostgreSQL for audit log)
    try:
        init_database(settings)
        await create_tables()
        audit_log = AuditLogService(settings)
        logger.info("database.postgres")
    except Exception as e:
        logger.warning("database.unavailable", error=str(e))
        audit_log = None

    # Connection pools
    try:
        init_pools(settings)
        logger.info("pools.initialized")
    except Exception as e:
        logger.warning("pools.init_failed", error=str(e))

    # ── Domain services ──────────────────────────────────────────────
    analytics_service = AnalyticsService(odoo_client)
    customer_service = CustomerService(odoo_client)
    document_service = DocumentService(qdrant_store)
    pricing_service = PricingService(odoo_client)
    supply_chain_service = SupplyChainService(odoo_client)

    # ── Agent graph (via builder) ────────────────────────────────────
    compiled_graph = build_graph(
        settings=settings,
        analytics_service=analytics_service,
        customer_service=customer_service,
        document_service=document_service,
        retriever=retriever,
        pricing_service=pricing_service,
        supply_chain_service=supply_chain_service,
    )

    # ── Store on app state ───────────────────────────────────────────
    app.state.settings = settings
    app.state.analytics_service = analytics_service
    app.state.customer_service = customer_service
    app.state.document_service = document_service
    app.state.pricing_service = pricing_service
    app.state.supply_chain_service = supply_chain_service
    app.state.qdrant_store = qdrant_store
    app.state.odoo_client = odoo_client
    app.state.compiled_graph = compiled_graph
    app.state.session_store = session_store
    app.state.embedding_service = embedding_service
    app.state.audit_log = audit_log
    app.state.get_pool_stats = get_pool_stats

    logger.info("app.started")

    yield

    # Shutdown
    logger.info("app.shutting_down")
    await close_database()


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.

    Returns:
        Configured FastAPI instance.
    """
    app = FastAPI(
        title="Basira API",
        description="Basira — Multi-Agent AI Platform for Retail & Food (Arabic-first)",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Authentication middleware (before rate limiting)
    app.add_middleware(AuthMiddleware)

    # Rate limiting middleware
    app.add_middleware(RateLimitMiddleware)

    # Include routers
    from src.api.routes.chat import router as chat_router
    from src.api.routes.analytics import router as analytics_router
    from src.api.routes.internal import router as internal_router
    from src.api.routes.health import router as health_router
    from src.api.routes.pricing import router as pricing_router
    from src.api.routes.supply_chain import router as supply_chain_router

    app.include_router(chat_router, prefix="/api/v1", tags=["Chat"])
    app.include_router(analytics_router, prefix="/api/v1", tags=["Analytics"])
    app.include_router(internal_router, prefix="/api/v1", tags=["Internal"])
    app.include_router(health_router, prefix="/api/v1", tags=["Health"])
    app.include_router(pricing_router, prefix="/api/v1", tags=["Pricing"])
    app.include_router(supply_chain_router, prefix="/api/v1", tags=["Supply Chain"])

    return app


# Module-level app instance for uvicorn
app = create_app()
