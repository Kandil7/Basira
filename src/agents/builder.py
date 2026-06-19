"""
Graph builder — factory for constructing the supervisor graph.

Provides a clean build_graph() entry point that wires agents, tools,
and services into the LangGraph supervisor. This is the single place
to configure the graph topology.

Phase 2: Added pricing and supply chain agent wiring.
"""

from typing import Any

import structlog

from src.agents.graph import build_supervisor_graph, compile_graph
from src.agents.state import AgentState
from src.config.settings import Settings
from src.domain.services.analytics_service import AnalyticsService
from src.domain.services.customer_service import CustomerService
from src.domain.services.document_service import DocumentService
from src.domain.services.pricing_service import PricingService
from src.domain.services.supply_chain_service import SupplyChainService
from src.infrastructure.rag.retriever import Retriever

logger = structlog.get_logger(__name__)


def build_graph(
    settings: Settings,
    analytics_service: AnalyticsService,
    customer_service: CustomerService,
    document_service: DocumentService,
    retriever: Retriever,
    pricing_service: PricingService | None = None,
    supply_chain_service: SupplyChainService | None = None,
) -> Any:
    """
    Build and compile the supervisor graph.

    This is the main factory function used by the FastAPI lifespan
    to construct the LangGraph supervisor with all dependencies wired.

    Flow:
        START → supervisor (classify intent)
                  ├─ analytics    → analytical_agent → END
                  ├─ cx           → cx_agent → END
                  ├─ internal_ops → internal_ops_agent → END
                  ├─ pricing      → pricing_agent → END
                  ├─ supply_chain → supply_chain_agent → END
                  └─ general      → general_agent → END

    Args:
        settings: Application settings (Groq API key, model, etc.)
        analytics_service: Domain service for sales/inventory analytics
        customer_service: Domain service for customer data (Odoo)
        document_service: Domain service for document processing (Qdrant)
        retriever: RAG retriever for semantic search
        pricing_service: Domain service for pricing (optional)
        supply_chain_service: Domain service for supply chain (optional)

    Returns:
        Compiled LangGraph ready for .ainvoke()
    """
    graph = build_supervisor_graph(
        settings=settings,
        analytics_service=analytics_service,
        customer_service=customer_service,
        document_service=document_service,
        retriever=retriever,
        pricing_service=pricing_service,
        supply_chain_service=supply_chain_service,
    )
    compiled = compile_graph(graph)

    agents = ["supervisor", "analytical_agent", "cx_agent", "internal_ops_agent", "general_agent"]
    if pricing_service is not None:
        agents.append("pricing_agent")
    if supply_chain_service is not None:
        agents.append("supply_chain_agent")

    logger.info(
        "builder.graph_ready",
        agents=agents,
        entry="supervisor",
    )

    return compiled
