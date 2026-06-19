"""
Multi-Agent Collaboration — agents can delegate to each other for complex queries.

Provides a delegation framework for agents to request help from other agents
when a query requires cross-domain expertise.
"""

from enum import Enum
from typing import Any, Callable, Awaitable

import structlog

logger = structlog.get_logger(__name__)


class DelegationReason(Enum):
    """Reasons for delegation."""
    CROSS_DOMAIN = "cross_domain"           # Query spans multiple domains
    DATA_REQUIRED = "data_required"         # Needs data from another agent's domain
    EXPERTISE_NEEDED = "expertise_needed"   # Requires specialized knowledge
    USER_REQUEST = "user_request"           # User explicitly asked for another agent


class DelegationRequest:
    """Request to delegate work to another agent."""

    def __init__(
        self,
        from_agent: str,
        to_agent: str,
        query: str,
        reason: DelegationReason,
        context: dict[str, Any] | None = None,
    ) -> None:
        self.from_agent = from_agent
        self.to_agent = to_agent
        self.query = query
        self.reason = reason
        self.context = context or {}
        self.result: str | None = None
        self.success: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "query": self.query,
            "reason": self.reason.value,
            "success": self.success,
        }


class AgentDelegator:
    """
    Multi-agent delegation manager.

    Allows agents to delegate queries to other agents when needed.
    """

    def __init__(self) -> None:
        self._agent_handlers: dict[str, Callable[..., Awaitable[dict[str, Any]]]] = {}
        self._delegation_history: list[DelegationRequest] = []
        self._max_delegation_depth = 3  # Prevent infinite loops

    def register_agent(
        self,
        agent_name: str,
        handler: Callable[..., Awaitable[dict[str, Any]]],
    ) -> None:
        """
        Register an agent handler for delegation.

        Args:
            agent_name: Name of the agent
            handler: Async function that handles queries
        """
        self._agent_handlers[agent_name] = handler
        logger.info("delegator.agent_registered", agent=agent_name)

    async def delegate(
        self,
        request: DelegationRequest,
        depth: int = 0,
    ) -> dict[str, Any]:
        """
        Delegate a query to another agent.

        Args:
            request: Delegation request
            depth: Current delegation depth (for loop prevention)

        Returns:
            Delegation result.
        """
        # Check delegation depth
        if depth >= self._max_delegation_depth:
            logger.warning(
                "delegator.max_depth",
                from_agent=request.from_agent,
                to_agent=request.to_agent,
                depth=depth,
            )
            return {
                "success": False,
                "error": "Maximum delegation depth reached",
                "agent": request.to_agent,
            }

        # Check if target agent is registered
        handler = self._agent_handlers.get(request.to_agent)
        if not handler:
            logger.warning(
                "delegator.agent_not_found",
                to_agent=request.to_agent,
            )
            return {
                "success": False,
                "error": f"Agent '{request.to_agent}' not found",
                "agent": request.to_agent,
            }

        # Execute delegation
        try:
            result = await handler(
                query=request.query,
                context=request.context,
                delegator=self,
                depth=depth + 1,
            )

            request.result = result.get("response", "")
            request.success = True
            self._delegation_history.append(request)

            logger.info(
                "delegator.success",
                from_agent=request.from_agent,
                to_agent=request.to_agent,
                query=request.query[:50],
            )

            return {
                "success": True,
                "response": request.result,
                "agent": request.to_agent,
                "reason": request.reason.value,
            }

        except Exception as e:
            logger.error(
                "delegator.failed",
                from_agent=request.from_agent,
                to_agent=request.to_agent,
                error=str(e),
            )
            return {
                "success": False,
                "error": str(e),
                "agent": request.to_agent,
            }

    def get_delegation_history(
        self,
        agent: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """
        Get delegation history.

        Args:
            agent: Filter by agent name
            limit: Maximum entries

        Returns:
            List of delegation records.
        """
        history = self._delegation_history
        if agent:
            history = [
                h for h in history
                if h.from_agent == agent or h.to_agent == agent
            ]
        return [h.to_dict() for h in history[-limit:]]

    def get_stats(self) -> dict[str, Any]:
        """Get delegation statistics."""
        total = len(self._delegation_history)
        successful = sum(1 for h in self._delegation_history if h.success)

        return {
            "total_delegations": total,
            "successful": successful,
            "failed": total - successful,
            "success_rate": successful / total if total > 0 else 0,
            "registered_agents": list(self._agent_handlers.keys()),
        }


class CollaborationRouter:
    """
    Routes complex queries to appropriate agent combinations.

    Analyzes queries to determine if collaboration is needed
    and which agents should be involved.
    """

    # Keywords that indicate cross-domain queries
    CROSS_DOMAIN_KEYWORDS = {
        ("pricing", "analytics"): ["سعر", "price", "مبيعات", "sales", "ربح", "margin"],
        ("supply_chain", "analytics"): ["مخزون", "inventory", "توريد", "supply", "طلب", "order"],
        ("cx", "supply_chain"): ["تتبع", "track", "توصيل", "delivery", "شحنة", "shipment"],
        ("pricing", "supply_chain"): ["تكلفة", "cost", "شراء", "purchase", "موردين", "supplier"],
    }

    def __init__(self) -> None:
        self._delegator = AgentDelegator()

    def analyze_query(self, query: str) -> list[str]:
        """
        Analyze a query to determine which agents are needed.

        Args:
            query: User query

        Returns:
            List of agent names that should handle the query.
        """
        query_lower = query.lower()
        agents_needed = set()

        for agent_pair, keywords in self.CROSS_DOMAIN_KEYWORDS.items():
            for keyword in keywords:
                if keyword in query_lower:
                    agents_needed.update(agent_pair)
                    break

        # Default to at least one agent
        if not agents_needed:
            return []

        return list(agents_needed)

    def should_collaborate(self, query: str) -> bool:
        """
        Determine if a query requires multi-agent collaboration.

        Args:
            query: User query

        Returns:
            True if collaboration is recommended.
        """
        agents = self.analyze_query(query)
        return len(agents) > 1

    async def collaborative_response(
        self,
        query: str,
        primary_agent: str,
        agent_handlers: dict[str, Callable[..., Awaitable[dict[str, Any]]]],
    ) -> dict[str, Any]:
        """
        Generate a collaborative response from multiple agents.

        Args:
            query: User query
            primary_agent: Primary agent handling the request
            agent_handlers: Dictionary of agent handlers

        Returns:
            Combined response from all agents.
        """
        agents_needed = self.analyze_query(query)

        if len(agents_needed) <= 1:
            # Single agent, no collaboration needed
            return {"collaboration": False, "agents": [primary_agent]}

        # Gather responses from all agents
        responses = {}
        for agent_name in agents_needed:
            if agent_name in agent_handlers:
                handler = agent_handlers[agent_name]
                try:
                    result = await handler(
                        query=query,
                        context={"collaboration": True, "other_agents": agents_needed},
                    )
                    responses[agent_name] = result.get("response", "")
                except Exception as e:
                    logger.warning(
                        "collaboration.agent_failed",
                        agent=agent_name,
                        error=str(e),
                    )

        # Combine responses
        combined_parts = []
        for agent_name, response in responses.items():
            if response:
                combined_parts.append(f"[{agent_name}]: {response}")

        combined_response = "\n\n".join(combined_parts) if combined_parts else ""

        return {
            "collaboration": True,
            "agents": list(responses.keys()),
            "responses": responses,
            "combined": combined_response,
        }


# Global instances
delegator = AgentDelegator()
collaboration_router = CollaborationRouter()
