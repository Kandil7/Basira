"""
Redis-backed session store for conversation history.

Provides persistent, scalable session management using Redis.
Falls back to in-memory store if Redis is unavailable.
"""

import json
import time
from typing import Any

import structlog

from src.config.settings import Settings

logger = structlog.get_logger(__name__)

DEFAULT_MAX_MESSAGES = 50
DEFAULT_SESSION_TTL = 3600  # 1 hour


class RedisSessionStore:
    """
    Redis-backed session store for conversation history.

    Provides persistent session storage with TTL-based expiration.
    Falls back to in-memory store if Redis connection fails.
    """

    def __init__(
        self,
        settings: Settings,
        max_messages: int = DEFAULT_MAX_MESSAGES,
    ) -> None:
        self._settings = settings
        self._max_messages = max_messages
        self._redis = None
        self._fallback: dict[str, dict] = {}
        self._connected = False

        self._connect()

    def _connect(self) -> None:
        """Initialize Redis connection."""
        try:
            import redis.asyncio as aioredis

            self._redis = aioredis.from_url(
                self._settings.redis_url,
                max_connections=self._settings.redis_max_connections,
                decode_responses=True,
            )
            self._connected = True
            logger.info(
                "redis.connected",
                url=self._settings.redis_url,
                max_connections=self._settings.redis_max_connections,
            )
        except ImportError:
            logger.warning("redis.missing_dep", dep="redis")
            self._connected = False
        except Exception as e:
            logger.warning("redis.connection_failed", error=str(e))
            self._connected = False

    def _session_key(self, session_id: str) -> str:
        """Generate Redis key for session."""
        return f"basira:session:{session_id}"

    async def get_or_create(self, session_id: str) -> dict[str, Any]:
        """Get an existing session or create a new one."""
        if not self._connected:
            return self._fallback_get_or_create(session_id)

        try:
            key = self._session_key(session_id)
            data = await self._redis.get(key)

            if data:
                session = json.loads(data)
                # Check TTL
                if time.time() - session.get("last_active", 0) > self._settings.redis_session_ttl:
                    await self._redis.delete(key)
                    logger.info("session.expired", session_id=session_id)
                    return self._create_session(session_id)
                return session
            else:
                return self._create_session(session_id)
        except Exception as e:
            logger.warning("redis.get_failed", error=str(e))
            return self._fallback_get_or_create(session_id)

    def _create_session(self, session_id: str) -> dict[str, Any]:
        """Create a new session."""
        return {
            "session_id": session_id,
            "messages": [],
            "metadata": {},
            "created_at": time.time(),
            "last_active": time.time(),
        }

    def _fallback_get_or_create(self, session_id: str) -> dict[str, Any]:
        """Fallback to in-memory store."""
        if session_id in self._fallback:
            return self._fallback[session_id]
        session = self._create_session(session_id)
        self._fallback[session_id] = session
        return session

    async def get_history(self, session_id: str) -> list[dict[str, Any]]:
        """Get message history for a session."""
        session = await self.get_or_create(session_id)
        messages = session.get("messages", [])
        return messages[-self._max_messages:]

    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        **kwargs: Any,
    ) -> None:
        """Add a message to a session."""
        session = await self.get_or_create(session_id)

        message = {
            "role": role,
            "content": content,
            "timestamp": time.time(),
            **kwargs,
        }

        session["messages"].append(message)
        session["last_active"] = time.time()

        # Trim old messages
        if len(session["messages"]) > self._max_messages:
            session["messages"] = session["messages"][-self._max_messages:]

        if not self._connected:
            self._fallback[session_id] = session
            return

        try:
            key = self._session_key(session_id)
            await self._redis.setex(
                key,
                self._settings.redis_session_ttl,
                json.dumps(session),
            )
        except Exception as e:
            logger.warning("redis.set_failed", error=str(e))
            self._fallback[session_id] = session

    async def delete(self, session_id: str) -> bool:
        """Delete a session."""
        if self._connected:
            try:
                key = self._session_key(session_id)
                await self._redis.delete(key)
                return True
            except Exception as e:
                logger.warning("redis.delete_failed", error=str(e))

        if session_id in self._fallback:
            del self._fallback[session_id]
            return True
        return False

    async def health_check(self) -> bool:
        """Check if Redis connection is alive."""
        if not self._connected or self._redis is None:
            return False
        try:
            await self._redis.ping()
            return True
        except Exception:
            return False

    @property
    def stats(self) -> dict[str, Any]:
        """Return store statistics."""
        return {
            "backend": "redis" if self._connected else "in-memory",
            "connected": self._connected,
            "fallback_sessions": len(self._fallback),
        }
