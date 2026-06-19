"""
LangGraph supervisor graph.

Builds the main agent graph with the supervisor routing to specialized
agent nodes based on intent classification.
"""

from typing import Any, Callable

from langgraph.graph import END, StateGraph

from src.agents.nodes.analytical import create_analytical_node
from src.agents.nodes.cx import create_cx_node
from src.agents.nodes.general import create_general_node
from src.agents.nodes.internal_ops import create_internal_ops_node
from src.agents.nodes.supervisor import create_supervisor_node
from src.agents.state import AgentState
from src.config.settings import Settings
from src.domain.services.analytics_service import AnalyticsService
from src.domain.services.customer_service import CustomerService
from src.domain.services.document_service import DocumentService
from src.infrastructure.rag.retriever import Retriever

import structlog

logger = structlog.get_logger(__name__)


def _route_by_intent(state: AgentState) -> str:
    """
    Route to the appropriate agent based on classified intent.

    Args:
        state: Current agent state with intent field

    Returns:
        Name of the next node to execute.
    """
    intent = state.get("intent", "general")
    routing_map = {
        "analytics": "analytical_agent",
        "cx": "cx_agent",
        "internal_ops": "internal_ops_agent",
    }
    return routing_map.get(intent, "general_agent")


def build_supervisor_graph(
    settings: Settings,
    analytics_service: AnalyticsService,
    customer_service: CustomerService,
    document_service: DocumentService,
    retriever: Retriever,
) -> StateGraph:
    """
    Build the complete supervisor agent graph.

    This graph:
    1. Starts at the supervisor node
    2. Classifies the user's intent
    3. Routes to the appropriate specialized agent
    4. Returns the response

    Args:
        settings: Application settings
        analytics_service: Analytics domain service
        customer_service: Customer service domain service
        document_service: Document processing domain service
        retriever: RAG retriever

    Returns:
        Compiled StateGraph ready for invocation.
    """
    # Create node functions with dependency injection
    supervisor = create_supervisor_node(settings)
    analytical = create_analytical_node(settings, analytics_service)
    cx = create_cx_node(settings, customer_service, retriever)
    internal_ops = create_internal_ops_node(settings, document_service)
    general = create_general_node(settings)

    # Build the graph
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("supervisor", supervisor)
    graph.add_node("analytical_agent", analytical)
    graph.add_node("cx_agent", cx)
    graph.add_node("internal_ops_agent", internal_ops)
    graph.add_node("general_agent", general)

    # Set entry point
    graph.set_entry_point("supervisor")

    # Add conditional routing from supervisor
    graph.add_conditional_edges(
        "supervisor",
        _route_by_intent,
        {
            "analytical_agent": "analytical_agent",
            "cx_agent": "cx_agent",
            "internal_ops_agent": "internal_ops_agent",
            "general_agent": "general_agent",
        },
    )

    # All agent nodes go to END
    graph.add_edge("analytical_agent", END)
    graph.add_edge("cx_agent", END)
    graph.add_edge("internal_ops_agent", END)
    graph.add_edge("general_agent", END)

    logger.info("supervisor_graph.built")
    return graph


def compile_graph(graph: StateGraph) -> Any:
    """
    Compile the graph for execution.

    Args:
        graph: The StateGraph to compile

    Returns:
        Compiled graph ready for .ainvoke()
    """
    compiled = graph.compile()
    logger.info("supervisor_graph.compiled")
    return compiled
