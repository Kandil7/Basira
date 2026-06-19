"""
Graph builder — factory for constructing the supervisor graph.

Provides a clean build_graph() entry point that wires agents, tools,
and services into the LangGraph supervisor. This is the single place
to configure the graph topology.
"""

from typing import Any

import structlog

from src.agents.graph import build_supervisor_graph, compile_graph
from src.agents.state import AgentState
from src.config.settings import Settings
from src.domain.services.analytics_service import AnalyticsService
from src.domain.services.customer_service import CustomerService
from src.domain.services.document_service import DocumentService
from src.infrastructure.rag.retriever import Retriever

logger = structlog.get_logger(__name__)


def build_graph(
    settings: Settings,
    analytics_service: AnalyticsService,
    customer_service: CustomerService,
    document_service: DocumentService,
    retriever: Retriever,
) -> Any:
    """
    Build and compile the supervisor graph.

    This is the main factory function used by the FastAPI lifespan
    to construct the LangGraph supervisor with all dependencies wired.

    Flow:
        START → supervisor (classify intent)
                  ├─ analytics  → analytical_agent → END
                  ├─ cx         → cx_agent → END
                  ├─ internal_ops → internal_ops_agent → END
                  └─ general    → general_agent → END

    Args:
        settings: Application settings (Groq API key, model, etc.)
        analytics_service: Domain service for sales/inventory analytics
        customer_service: Domain service for customer data (Odoo)
        document_service: Domain service for document processing (Qdrant)
        retriever: RAG retriever for semantic search

    Returns:
        Compiled LangGraph ready for .ainvoke()

    Example:
        graph = build_graph(settings, analytics_svc, cx_svc, doc_svc, retriever)
        result = await graph.ainvoke(create_initial_state("ما هي مبيعات اليوم؟"))
    """
    graph = build_supervisor_graph(
        settings=settings,
        analytics_service=analytics_service,
        customer_service=customer_service,
        document_service=document_service,
        retriever=retriever,
    )
    compiled = compile_graph(graph)

    logger.info(
        "builder.graph_ready",
        nodes=["supervisor", "analytical_agent", "cx_agent", "internal_ops_agent", "general_agent"],
        entry="supervisor",
    )

    return compiled
