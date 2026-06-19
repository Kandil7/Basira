"""
In-memory session store for conversation history.

Provides per-session message history for multi-turn conversations.
Phase 1: In-memory store. Production: Replace with Redis/DB.
"""

import time
from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

DEFAULT_MAX_MESSAGES = 50
DEFAULT_SESSION_TTL = 3600  # 1 hour


@dataclass
class SessionMessage:
    """A single message in a session."""

    role: str  # "user" or "assistant"
    content: str
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Session:
    """A conversation session with message history."""

    session_id: str
    messages: list[SessionMessage] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)

    @property
    def message_count(self) -> int:
        return len(self.messages)

    def add_message(self, role: str, content: str, **kwargs: Any) -> None:
        """Add a message to the session."""
        self.messages.append(
            SessionMessage(role=role, content=content, metadata=kwargs)
        )
        self.last_active = time.time()

    def get_history(self, limit: int = DEFAULT_MAX_MESSAGES) -> list[dict[str, Any]]:
        """Get recent message history as list of dicts."""
        recent = self.messages[-limit:]
        return [
            {"role": msg.role, "content": msg.content}
            for msg in recent
        ]

    def is_expired(self, ttl: int = DEFAULT_SESSION_TTL) -> bool:
        """Check if session has expired."""
        return (time.time() - self.last_active) > ttl


class SessionStore:
    """
    In-memory session store.

    Manages conversation sessions with configurable TTL and message limits.
    """

    def __init__(
        self,
        max_sessions: int = 1000,
        session_ttl: int = DEFAULT_SESSION_TTL,
        max_messages: int = DEFAULT_MAX_MESSAGES,
    ) -> None:
        self._sessions: dict[str, Session] = {}
        self._max_sessions = max_sessions
        self._session_ttl = session_ttl
        self._max_messages = max_messages
        logger.info(
            "session_store.initialized",
            max_sessions=max_sessions,
            session_ttl=session_ttl,
        )

    def get_or_create(self, session_id: str) -> Session:
        """Get an existing session or create a new one."""
        # Clean expired sessions periodically
        self._cleanup_expired()

        if session_id in self._sessions:
            session = self._sessions[session_id]
            if session.is_expired(self._session_ttl):
                logger.info("session.expired", session_id=session_id)
                del self._sessions[session_id]
            else:
                return session

        # Enforce max sessions
        if len(self._sessions) >= self._max_sessions:
            self._evict_oldest()

        session = Session(session_id=session_id)
        self._sessions[session_id] = session
        logger.info("session.created", session_id=session_id)
        return session

    def get_history(self, session_id: str) -> list[dict[str, Any]]:
        """Get message history for a session."""
        session = self._sessions.get(session_id)
        if session is None or session.is_expired(self._session_ttl):
            return []
        return session.get_history(self._max_messages)

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        **kwargs: Any,
    ) -> None:
        """Add a message to a session."""
        session = self.get_or_create(session_id)
        session.add_message(role, content, **kwargs)

    def delete(self, session_id: str) -> bool:
        """Delete a session."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def _cleanup_expired(self) -> None:
        """Remove expired sessions."""
        expired = [
            sid for sid, s in self._sessions.items()
            if s.is_expired(self._session_ttl)
        ]
        for sid in expired:
            del self._sessions[sid]
        if expired:
            logger.info("session.cleanup", count=len(expired))

    def _evict_oldest(self) -> None:
        """Evict the oldest inactive session."""
        if not self._sessions:
            return
        oldest_id = min(self._sessions, key=lambda k: self._sessions[k].last_active)
        del self._sessions[oldest_id]
        logger.info("session.evicted", session_id=oldest_id)

    @property
    def stats(self) -> dict[str, Any]:
        """Return store statistics."""
        return {
            "active_sessions": len(self._sessions),
            "max_sessions": self._max_sessions,
        }
