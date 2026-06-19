"""
Audit log service — persistent audit trail for agent actions.

Records all agent interactions, tool calls, and decisions to PostgreSQL
for compliance, debugging, and analytics.
"""

import json
from datetime import datetime, timezone
from typing import Any

import structlog

from src.config.settings import Settings
from src.infrastructure.database.models import AuditLog, get_session

logger = structlog.get_logger(__name__)


class AuditLogService:
    """
    Audit log service for recording agent actions.

    Provides async logging of all agent interactions to PostgreSQL.
    Gracefully handles database failures without blocking agent responses.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._enabled = settings.app_env != "test"

    async def log_interaction(
        self,
        session_id: str | None,
        user_query: str,
        agent: str,
        intent: str,
        response: str,
        tools_used: list[str] | None = None,
        sources: list[str] | None = None,
        processing_time_ms: float | None = None,
        success: bool = True,
        error_message: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Log an agent interaction to the audit trail.

        Args:
            session_id: Session identifier
            user_query: Original user query
            agent: Which agent handled the request
            intent: Classified intent
            response: Agent response
            tools_used: List of tools invoked
            sources: Source references
            processing_time_ms: Processing time in milliseconds
            success: Whether the interaction was successful
            error_message: Error message if failed
            metadata: Additional metadata
        """
        if not self._enabled:
            return

        try:
            session = get_session()
            if session is None:
                logger.debug("audit.db_unavailable")
                return

            log_entry = AuditLog(
                timestamp=datetime.now(timezone.utc),
                session_id=session_id,
                user_query=user_query[:2000] if user_query else None,
                agent=agent,
                intent=intent,
                response=response[:5000] if response else None,
                tools_used=json.dumps(tools_used) if tools_used else None,
                sources=json.dumps(sources) if sources else None,
                processing_time_ms=processing_time_ms,
                success=1 if success else 0,
                error_message=error_message[:1000] if error_message else None,
                metadata_json=json.dumps(metadata) if metadata else None,
            )

            session.add(log_entry)
            await session.commit()

            logger.debug(
                "audit.logged",
                agent=agent,
                intent=intent,
                success=success,
            )

        except Exception as e:
            logger.warning("audit.log_failed", error=str(e))
            # Don't let audit failures block the response

    async def get_recent_logs(
        self,
        agent: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Get recent audit log entries.

        Args:
            agent: Optional agent filter
            limit: Maximum entries to return

        Returns:
            List of audit log entries as dictionaries.
        """
        try:
            from sqlalchemy import select

            session = get_session()
            if session is None:
                return []

            query = select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit)
            if agent:
                query = query.where(AuditLog.agent == agent)

            result = await session.execute(query)
            logs = result.scalars().all()

            return [
                {
                    "id": log.id,
                    "timestamp": log.timestamp.isoformat(),
                    "session_id": log.session_id,
                    "agent": log.agent,
                    "intent": log.intent,
                    "processing_time_ms": log.processing_time_ms,
                    "success": log.success == 1,
                }
                for log in logs
            ]

        except Exception as e:
            logger.warning("audit.query_failed", error=str(e))
            return []

    async def get_stats(
        self,
        hours: int = 24,
    ) -> dict[str, Any]:
        """
        Get audit statistics for the last N hours.

        Args:
            hours: Number of hours to look back

        Returns:
            Statistics dictionary.
        """
        try:
            from sqlalchemy import func, select

            session = get_session()
            if session is None:
                return {}

            cutoff = datetime.now(timezone.utc).replace(
                hour=datetime.now(timezone.utc).hour - hours
            )

            # Total interactions
            total_query = select(func.count(AuditLog.id)).where(
                AuditLog.timestamp >= cutoff
            )
            total_result = await session.execute(total_query)
            total = total_result.scalar() or 0

            # Success rate
            success_query = select(func.count(AuditLog.id)).where(
                AuditLog.timestamp >= cutoff,
                AuditLog.success == 1,
            )
            success_result = await session.execute(success_query)
            success = success_result.scalar() or 0

            # Average processing time
            avg_time_query = select(func.avg(AuditLog.processing_time_ms)).where(
                AuditLog.timestamp >= cutoff
            )
            avg_time_result = await session.execute(avg_time_query)
            avg_time = avg_time_result.scalar() or 0

            return {
                "total_interactions": total,
                "successful": success,
                "failed": total - success,
                "success_rate": success / total if total > 0 else 0,
                "avg_processing_time_ms": round(avg_time, 2),
                "period_hours": hours,
            }

        except Exception as e:
            logger.warning("audit.stats_failed", error=str(e))
            return {}
