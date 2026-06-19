"""
Shared agent state definition for LangGraph.

All agent nodes share this state schema. The supervisor updates the
'intent' field to route to the appropriate agent.

Phase 3 enhancements:
- Added 'user_query' for raw input access
- Added 'agent' to identify which agent handled the request
- Added 'sources' for RAG attribution
"""

from typing import Annotated, Any, Literal

from langgraph.graph import add_messages


class AgentState(dict):  # type: ignore[type-arg]
    """
    Shared state across all agent nodes in the LangGraph supervisor.

    Attributes:
        messages: Conversation history (managed by LangGraph add_messages)
        user_query: Raw user input text (preserved for logging/debugging)
        task: Current task/purpose being handled
        intent: Classified intent (analytics, cx, internal_ops, general)
        agent: Which agent handled this request (analytical, cx, internal_ops, general)
        context: RAG-retrieved context from Qdrant
        response: Final agent response text
        sources: List of source references (doc IDs, URLs, etc.)
        metadata: Channel, user info, timestamps
        tools_used: Audit trail of tools called during this turn
        error: Error message if any step failed
    """

    def __init__(self, **kwargs: Any) -> None:
        defaults = {
            "messages": [],
            "user_query": "",
            "task": "",
            "intent": "general",
            "agent": None,
            "context": {},
            "response": "",
            "sources": [],
            "metadata": {},
            "tools_used": [],
            "error": None,
        }
        defaults.update(kwargs)
        super().__init__(defaults)

    # ── Typed accessors for IDE support ──────────────────────────────

    @property
    def user_query(self) -> str:
        """Raw user input text."""
        return self.get("user_query", "")

    @property
    def intent(self) -> str:
        """Classified intent."""
        return self.get("intent", "general")

    @property
    def agent(self) -> str | None:
        """Which agent handled this request."""
        return self.get("agent")

    @property
    def response(self) -> str:
        """Final agent response."""
        return self.get("response", "")

    @property
    def sources(self) -> list[str]:
        """Source references for RAG attribution."""
        return self.get("sources", [])

    @property
    def tools_used(self) -> list[str]:
        """Audit trail of tools called."""
        return self.get("tools_used", [])

    @property
    def error(self) -> str | None:
        """Error message if failed."""
        return self.get("error")


def create_initial_state(query: str, metadata: dict[str, Any] | None = None) -> AgentState:
    """
    Create an initial AgentState for a new conversation turn.

    Args:
        query: User's input message
        metadata: Optional metadata (channel, user_id, etc.)

    Returns:
        Fresh AgentState ready for the supervisor graph.
    """
    return AgentState(
        messages=[{"role": "user", "content": query}],
        user_query=query,
        task="",
        intent="general",
        agent=None,
        context={},
        response="",
        sources=[],
        metadata=metadata or {},
        tools_used=[],
        error=None,
    )
