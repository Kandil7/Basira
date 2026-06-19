"""
Agent Context — context-aware responses based on conversation history and preferences.

Provides context enrichment for agent responses to make them more personalized
and relevant to the user's needs.
"""

from typing import Any

import structlog

from src.infrastructure.memory import ConversationMemory, ContextBuilder

logger = structlog.get_logger(__name__)


class AgentContextManager:
    """
    Manages context for agent responses.

    Enriches queries with conversation history, user preferences,
    and relevant past interactions for better responses.
    """

    def __init__(self, memory: ConversationMemory | None = None) -> None:
        self._memory = memory or ConversationMemory()
        self._context_builder = ContextBuilder(self._memory)

    async def enrich_query(
        self,
        session_id: str,
        user_id: str | None,
        query: str,
        agent: str,
    ) -> dict[str, Any]:
        """
        Enrich a query with context for better responses.

        Args:
            session_id: Current session ID
            user_id: User ID (optional)
            query: User query
            agent: Target agent

        Returns:
            Enriched context dictionary.
        """
        # Build base context
        context = await self._context_builder.build_context(
            session_id, user_id, query
        )

        # Add agent-specific context
        context["agent"] = agent
        context["enrichments"] = []

        # Check if user has preferences for this agent
        if user_id:
            agent_prefs = await self._memory.get_preference(
                user_id, f"agent_{agent}_prefs", {}
            )
            if agent_prefs:
                context["agent_preferences"] = agent_prefs
                context["enrichments"].append("agent_preferences")

        # Check conversation history for continuity
        history = context.get("recent_history", [])
        if history:
            # Detect follow-up queries
            if self._is_follow_up(query, history):
                context["is_follow_up"] = True
                context["enrichments"].append("follow_up_detection")

            # Detect topic continuation
            last_topic = self._extract_topic(history)
            if last_topic and self._is_topic_related(query, last_topic):
                context["topic_continuation"] = last_topic
                context["enrichments"].append("topic_continuation")

        # Add user context
        if user_id:
            user_ctx = await self._memory.get_user_context(user_id)
            context["user_expertise"] = self._estimate_expertise(user_ctx)
            context["enrichments"].append("user_expertise")

        logger.debug(
            "context.enriched",
            agent=agent,
            enrichments=context["enrichments"],
        )

        return context

    async def record_interaction(
        self,
        session_id: str,
        user_id: str | None,
        query: str,
        response: str,
        agent: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Record an interaction in memory.

        Args:
            session_id: Session ID
            user_id: User ID (optional)
            query: User query
            response: Agent response
            agent: Agent name
            metadata: Additional metadata
        """
        # Record user message
        await self._memory.add_message(
            session_id=session_id,
            user_id=user_id,
            role="user",
            content=query,
            metadata=metadata,
        )

        # Record assistant response
        await self._memory.add_message(
            session_id=session_id,
            user_id=user_id,
            role="assistant",
            content=response,
            agent=agent,
            metadata=metadata,
        )

        # Update user preferences based on interaction
        if user_id:
            await self._update_user_preferences(user_id, query, agent)

    def _is_follow_up(self, query: str, history: list[dict[str, Any]]) -> bool:
        """Detect if query is a follow-up to previous conversation."""
        follow_up_indicators = [
            "و", "أيضاً", "also", "more", "تفضل", "please",
            "ماذا عن", "what about", "كيف", "how about",
            "هل يمكن", "can you", "أريد", "I want",
        ]

        query_lower = query.lower()
        return any(indicator in query_lower for indicator in follow_up_indicators)

    def _extract_topic(self, history: list[dict[str, Any]]) -> str | None:
        """Extract the main topic from conversation history."""
        if not history:
            return None

        # Get last user message
        for msg in reversed(history):
            if msg.get("role") == "user":
                content = msg.get("content", "").lower()
                # Simple topic extraction
                if any(w in content for w in ["مبيعات", "sales", "revenue"]):
                    return "sales"
                elif any(w in content for w in ["مخزون", "inventory", "stock"]):
                    return "inventory"
                elif any(w in content for w in ["سعر", "price", "pricing"]):
                    return "pricing"
                elif any(w in content for w in ["توريد", "supply", "supplier"]):
                    return "supply_chain"
                elif any(w in content for w in ["عميل", "customer", "order"]):
                    return "customer_service"
                return content[:50]

        return None

    def _is_topic_related(self, query: str, topic: str) -> bool:
        """Check if query is related to the given topic."""
        topic_keywords = {
            "sales": ["مبيعات", "sales", "revenue", "أرباح", "profit"],
            "inventory": ["مخزون", "inventory", "stock", "מלאי"],
            "pricing": ["سعر", "price", "pricing", "خصم", "discount"],
            "supply_chain": ["توريد", "supply", "supplier", "موردين"],
            "customer_service": ["عميل", "customer", "order", "طلب"],
        }

        query_lower = query.lower()
        keywords = topic_keywords.get(topic, [])

        return any(kw in query_lower for kw in keywords)

    def _estimate_expertise(self, user_context: dict[str, Any]) -> str:
        """Estimate user expertise level based on history."""
        total_messages = user_context.get("total_messages", 0)

        if total_messages > 50:
            return "expert"
        elif total_messages > 10:
            return "intermediate"
        else:
            return "beginner"

    async def _update_user_preferences(
        self,
        user_id: str,
        query: str,
        agent: str,
    ) -> None:
        """Update user preferences based on interaction."""
        # Track agent usage
        current = await self._memory.get_preference(user_id, "agent_usage", {})
        current[agent] = current.get(agent, 0) + 1
        await self._memory.update_preferences(user_id, {"agent_usage": current})

        # Detect language preference
        arabic_chars = sum(1 for c in query if '\u0600' <= c <= '\u06FF')
        if arabic_chars > len(query) * 0.3:
            await self._memory.update_preferences(user_id, {"language": "ar"})
        else:
            await self._memory.update_preferences(user_id, {"language": "en"})


# Global instance
agent_context_manager = AgentContextManager()
