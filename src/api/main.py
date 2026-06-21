"""
FastAPI application factory.

Creates and configures the FastAPI app with all routes, middleware,
and dependency injection.

Production: Integrated production embeddings, vector store, cache, and rate limiter.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.agents.builder import build_graph
from src.api.middleware.auth import AuthMiddleware
from src.api.middleware.guardrails import GuardrailsMiddleware
from src.api.middleware.rbac import RBACMiddleware
from src.config.settings import Settings, get_settings
from src.infrastructure.data.odoo_client import OdooClient
from src.infrastructure.logging.config import setup_logging
from src.infrastructure.rag.retriever import Retriever
from src.infrastructure.rag.vectorstore import ProductionVectorStore
from src.infrastructure.embeddings.service import EmbeddingService
from src.infrastructure.cache.cache import MultiTierCache
from src.infrastructure.ratelimit.limiter import RateLimiter, RateLimitConfig
from src.infrastructure.ratelimit.middleware import ProductionRateLimitMiddleware
from src.infrastructure.voice.asr import SpeechRecognizer
from src.infrastructure.voice.tts import SpeechSynthesizer
from src.infrastructure.voice.pipeline import VoicePipeline
from src.infrastructure.session.redis_store import RedisSessionStore
from src.infrastructure.session.session_store import SessionStore
from src.infrastructure.database.audit import AuditLogService
from src.infrastructure.database.models import init_database, create_tables, close_database
from src.infrastructure.pooling import init_pools, get_pool_stats
from src.infrastructure.memory import ConversationMemory, ContextBuilder
from src.infrastructure.agent_context import AgentContextManager
from src.infrastructure.collaboration import AgentDelegator, CollaborationRouter
from src.infrastructure.metrics import MetricsCollector
from src.infrastructure.observability import init_telemetry, AgentMetrics
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

    Initializes all production infrastructure and builds the agent graph.
    """
    settings = get_settings()

    setup_logging(settings.app_log_level)
    logger.info("app.starting", env=settings.app_env)

    # ── Redis (shared across all services) ────────────────────────────
    redis_client = None
    try:
        import redis.asyncio as aioredis
        redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
        await redis_client.ping()
        logger.info("redis.connected")
    except Exception:
        logger.warning("redis.unavailable", fallback="in-memory")

    # ── Vector Store (production) ─────────────────────────────────────
    qdrant_store = ProductionVectorStore(settings)

    # ── Embeddings (multi-provider with cache) ────────────────────────
    embedding_service = EmbeddingService(settings, redis_client=redis_client)

    # ── Multi-tier Cache ──────────────────────────────────────────────
    cache = MultiTierCache(
        redis_url=settings.redis_url,
        namespace="basira",
        l1_max_size=1000,
        l1_ttl=300,    # L1: 5 min
        l2_ttl=3600,   # L2: 1 hour
    )

    # ── Rate Limiter ──────────────────────────────────────────────────
    rate_limit_config = RateLimitConfig(
        default_limit=60,
        default_window=60,
        endpoint_limits={
            "/api/v1/chat": {"limit": 30, "window": 60},
            "/api/v1/reports": {"limit": 10, "window": 60},
            "/api/v1/export": {"limit": 5, "window": 60},
        },
        role_limits={
            "admin": {"limit": 200, "window": 60},
            "analyst": {"limit": 100, "window": 60},
            "viewer": {"limit": 30, "window": 60},
        },
        algorithm="sliding_window",
    )
    rate_limiter = RateLimiter(config=rate_limit_config)

    # ── Retriever ─────────────────────────────────────────────────────
    retriever = Retriever(qdrant_store, settings, embedding_service)

    # ── Session store (Redis with in-memory fallback) ─────────────────
    try:
        session_store = RedisSessionStore(settings)
        logger.info("session_store.redis")
    except Exception as e:
        logger.warning("session_store.fallback", error=str(e))
        session_store = SessionStore()

    # ── Database (PostgreSQL for audit log) ───────────────────────────
    try:
        init_database(settings)
        await create_tables()
        audit_log = AuditLogService(settings)
        logger.info("database.postgres")
    except Exception as e:
        logger.warning("database.unavailable", error=str(e))
        audit_log = None

    # ── Connection pools ──────────────────────────────────────────────
    try:
        init_pools(settings)
        logger.info("pools.initialized")
    except Exception as e:
        logger.warning("pools.init_failed", error=str(e))

    # ── Odoo client ───────────────────────────────────────────────────
    odoo_client = OdooClient(settings)

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

    # ── Voice Pipeline (ASR + TTS) ────────────────────────────────────
    voice_pipeline = None
    groq_api_key = settings.groq_api_key
    if groq_api_key and groq_api_key != "change-me":
        try:
            asr = SpeechRecognizer(
                api_key=groq_api_key,
                model="whisper-large-v3",
                base_url=settings.groq_base_url,
            )
            tts = SpeechSynthesizer(
                api_key=groq_api_key,
                model="canopylabs/orpheus-arabic-saudi",
                base_url=settings.groq_base_url,
            )

            # Create agent function wrapper for voice pipeline
            async def voice_agent_fn(query: str, session_id: str | None = None) -> dict:
                from src.agents.state import create_initial_state
                state = create_initial_state(query, session_id=session_id)
                result = await compiled_graph.ainvoke(state)
                return {
                    "response": result.get("response", ""),
                    "intent": result.get("intent", "unknown"),
                    "agent": result.get("agent", "unknown"),
                }

            voice_pipeline = VoicePipeline(
                asr=asr,
                tts=tts,
                agent_fn=voice_agent_fn,
            )
            logger.info("voice.pipeline_initialized")
        except Exception as e:
            logger.warning("voice.pipeline_init_failed", error=str(e))
    else:
        logger.warning("voice.pipeline_skipped", reason="No Groq API key configured")

    # ── Memory & Context ───────────────────────────────────────────────
    conversation_memory = ConversationMemory(settings)
    context_builder = ContextBuilder(conversation_memory)
    agent_context = AgentContextManager(conversation_memory)

    # ── Collaboration ──────────────────────────────────────────────────
    delegator = AgentDelegator()
    collaboration_router = CollaborationRouter()

    # ── Metrics & Observability ────────────────────────────────────────
    metrics_collector = MetricsCollector()
    agent_metrics = AgentMetrics()

    # Initialize OpenTelemetry (optional)
    try:
        init_telemetry(service_name="basira-api", enabled=True)
    except Exception:
        logger.warning("telemetry.init_skipped")

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
    app.state.cache = cache
    app.state.rate_limiter = rate_limiter
    app.state.audit_log = audit_log
    app.state.redis_client = redis_client
    app.state.voice_pipeline = voice_pipeline
    app.state.conversation_memory = conversation_memory
    app.state.context_builder = context_builder
    app.state.agent_context = agent_context
    app.state.delegator = delegator
    app.state.collaboration_router = collaboration_router
    app.state.metrics_collector = metrics_collector
    app.state.agent_metrics = agent_metrics
    app.state.get_pool_stats = get_pool_stats

    logger.info(
        "app.started",
        embedding_provider=embedding_service.provider_name,
        cache_l1_size=1000,
        rate_limit_algorithm=rate_limit_config.algorithm,
    )

    yield

    # Shutdown
    logger.info("app.shutting_down")
    await close_database()
    if redis_client:
        await redis_client.close()


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.

    Returns:
        Configured FastAPI instance.
    """
    app = FastAPI(
        title="Basira API",
        description="Basira — Multi-Agent AI Platform for Retail & Food (Arabic-first)",
        version="1.0.0",
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

    # Production rate limiting middleware
    app.add_middleware(ProductionRateLimitMiddleware)

    # Guardrails middleware
    app.add_middleware(GuardrailsMiddleware)

    # RBAC middleware
    app.add_middleware(RBACMiddleware)

    # Include routers
    from src.api.routes.chat import router as chat_router
    from src.api.routes.analytics import router as analytics_router
    from src.api.routes.internal import router as internal_router
    from src.api.routes.health import router as health_router
    from src.api.routes.pricing import router as pricing_router
    from src.api.routes.supply_chain import router as supply_chain_router
    from src.api.routes.export import router as export_router
    from src.api.routes.escalation import router as escalation_router
    from src.api.routes.voice import router as voice_router

    app.include_router(chat_router, prefix="/api/v1", tags=["Chat"])
    app.include_router(analytics_router, prefix="/api/v1", tags=["Analytics"])
    app.include_router(internal_router, prefix="/api/v1", tags=["Internal"])
    app.include_router(health_router, prefix="/api/v1", tags=["Health"])
    app.include_router(pricing_router, prefix="/api/v1", tags=["Pricing"])
    app.include_router(supply_chain_router, prefix="/api/v1", tags=["Supply Chain"])
    app.include_router(export_router, prefix="/api/v1", tags=["Export"])
    app.include_router(escalation_router, prefix="/api/v1", tags=["Escalation"])
    app.include_router(voice_router, prefix="/api/v1", tags=["Voice"])

    return app


# Module-level app instance for uvicorn
app = create_app()
