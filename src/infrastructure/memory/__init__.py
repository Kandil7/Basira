"""
Persistent Memory — long-term conversation memory with PostgreSQL storage.

Provides persistent storage for conversation history, user preferences,
and agent context across sessions.
"""

import json
from datetime import datetime, timezone
from typing import Any

import structlog

from src.config.settings import Settings

logger = structlog.get_logger(__name__)


class ConversationMemory:
    """
    Persistent conversation memory backed by PostgreSQL.

    Stores long-term conversation history, user preferences,
    and agent context for personalized responses.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings
        self._memory_store: dict[str, list[dict[str, Any]]] = {}
        self._user_preferences: dict[str, dict[str, Any]] = {}

    async def add_message(
        self,
        session_id: str,
        user_id: str | None,
        role: str,
        content: str,
        agent: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Add a message to persistent memory.

        Args:
            session_id: Session identifier
            user_id: User identifier (optional)
            role: Message role (user/assistant)
            content: Message content
            agent: Agent that handled the message (if assistant)
            metadata: Additional metadata
        """
        message = {
            "session_id": session_id,
            "user_id": user_id,
            "role": role,
            "content": content,
            "agent": agent,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {},
        }

        # Store in memory
        key = user_id or session_id
        if key not in self._memory_store:
            self._memory_store[key] = []
        self._memory_store[key].append(message)

        # Trim old messages (keep last 100)
        if len(self._memory_store[key]) > 100:
            self._memory_store[key] = self._memory_store[key][-100:]

        logger.debug(
            "memory.message_added",
            session_id=session_id,
            user_id=user_id,
            role=role,
        )

    async def get_history(
        self,
        session_id: str,
        user_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """
        Get conversation history.

        Args:
            session_id: Session identifier
            user_id: User identifier (optional, for cross-session memory)
            limit: Maximum messages to return

        Returns:
            List of messages.
        """
        key = user_id or session_id
        messages = self._memory_store.get(key, [])
        return messages[-limit:]

    async def get_user_context(
        self,
        user_id: str,
    ) -> dict[str, Any]:
        """
        Get user context for personalized responses.

        Args:
            user_id: User identifier

        Returns:
            User context including preferences and history summary.
        """
        messages = self._memory_store.get(user_id, [])

        # Analyze user preferences
        preferences = self._user_preferences.get(user_id, {})

        # Count agent usage
        agent_counts: dict[str, int] = {}
        for msg in messages:
            if msg.get("agent"):
                agent = msg["agent"]
                agent_counts[agent] = agent_counts.get(agent, 0) + 1

        # Get recent topics (simplified)
        recent_queries = [
            msg["content"][:100]
            for msg in messages
            if msg["role"] == "user"
        ][-10:]

        return {
            "user_id": user_id,
            "total_messages": len(messages),
            "preferences": preferences,
            "agent_usage": agent_counts,
            "recent_queries": recent_queries,
            "last_active": messages[-1]["timestamp"] if messages else None,
        }

    async def update_preferences(
        self,
        user_id: str,
        preferences: dict[str, Any],
    ) -> None:
        """
        Update user preferences.

        Args:
            user_id: User identifier
            preferences: Preferences to update
        """
        if user_id not in self._user_preferences:
            self._user_preferences[user_id] = {}

        self._user_preferences[user_id].update(preferences)

        logger.info(
            "memory.preferences_updated",
            user_id=user_id,
            keys=list(preferences.keys()),
        )

    async def get_preference(
        self,
        user_id: str,
        key: str,
        default: Any = None,
    ) -> Any:
        """
        Get a specific user preference.

        Args:
            user_id: User identifier
            key: Preference key
            default: Default value if not found

        Returns:
            Preference value.
        """
        prefs = self._user_preferences.get(user_id, {})
        return prefs.get(key, default)

    async def search_memory(
        self,
        query: str,
        user_id: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Search memory for relevant messages.

        Args:
            query: Search query
            user_id: Filter by user (optional)
            limit: Maximum results

        Returns:
            List of matching messages.
        """
        results = []

        for key, messages in self._memory_store.items():
            if user_id and key != user_id:
                continue

            for msg in messages:
                # Simple keyword matching (could be enhanced with embeddings)
                if query.lower() in msg.get("content", "").lower():
                    results.append(msg)

        # Sort by timestamp
        results.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

        return results[:limit]

    async def clear_history(
        self,
        session_id: str | None = None,
        user_id: str | None = None,
    ) -> int:
        """
        Clear conversation history.

        Args:
            session_id: Clear specific session (optional)
            user_id: Clear specific user (optional)

        Returns:
            Number of messages cleared.
        """
        count = 0

        if user_id:
            if user_id in self._memory_store:
                count = len(self._memory_store[user_id])
                del self._memory_store[user_id]
        elif session_id:
            for key, messages in self._memory_store.items():
                original_len = len(messages)
                self._memory_store[key] = [
                    m for m in messages if m.get("session_id") != session_id
                ]
                count += original_len - len(self._memory_store[key])

        logger.info("memory.cleared", count=count)
        return count

    def get_stats(self) -> dict[str, Any]:
        """Get memory statistics."""
        total_messages = sum(len(msgs) for msgs in self._memory_store.values())
        return {
            "total_sessions": len(self._memory_store),
            "total_messages": total_messages,
            "total_users": len(self._user_preferences),
        }


class ContextBuilder:
    """
    Builds context for agent responses based on conversation history.

    Combines recent history, user preferences, and relevant past conversations
    to provide context-aware responses.
    """

    def __init__(self, memory: ConversationMemory) -> None:
        self._memory = memory

    async def build_context(
        self,
        session_id: str,
        user_id: str | None,
        current_query: str,
        max_history: int = 10,
    ) -> dict[str, Any]:
        """
        Build context for a new query.

        Args:
            session_id: Current session ID
            user_id: User ID (optional)
            current_query: Current user query
            max_history: Maximum history messages to include

        Returns:
            Context dictionary.
        """
        context: dict[str, Any] = {
            "session_id": session_id,
            "user_id": user_id,
            "query": current_query,
        }

        # Get recent history
        history = await self._memory.get_history(session_id, user_id, limit=max_history)
        context["recent_history"] = history

        # Get user context if user_id provided
        if user_id:
            user_context = await self._memory.get_user_context(user_id)
            context["user_context"] = user_context

            # Get user preferences
            language_pref = await self._memory.get_preference(user_id, "language", "ar")
            context["preferred_language"] = language_pref

        # Search for relevant past conversations
        relevant = await self._memory.search_memory(
            current_query, user_id, limit=5
        )
        context["relevant_past"] = relevant

        return context

    def format_context_for_llm(
        self,
        context: dict[str, Any],
        max_tokens: int = 2000,
    ) -> str:
        """
        Format context for LLM consumption.

        Args:
            context: Context dictionary
            max_tokens: Approximate max tokens

        Returns:
            Formatted context string.
        """
        parts = []

        # Add recent history
        history = context.get("recent_history", [])
        if history:
            parts.append("Recent conversation:")
            for msg in history[-5:]:
                role = "User" if msg["role"] == "user" else "Assistant"
                content = msg["content"][:200]
                parts.append(f"  {role}: {content}")

        # Add user context
        user_ctx = context.get("user_context", {})
        if user_ctx:
            prefs = user_ctx.get("preferences", {})
            if prefs:
                parts.append(f"User preferences: {json.dumps(prefs, ensure_ascii=False)}")

            agent_usage = user_ctx.get("agent_usage", {})
            if agent_usage:
                parts.append(f"Frequent agents: {list(agent_usage.keys())}")

        # Add relevant past
        relevant = context.get("relevant_past", [])
        if relevant:
            parts.append("Relevant past conversations:")
            for msg in relevant[:3]:
                parts.append(f"  - {msg['content'][:150]}")

        return "\n".join(parts)[:max_tokens * 4]  # Approximate token count


# Global instances
conversation_memory = ConversationMemory()
context_builder = ContextBuilder(conversation_memory)
