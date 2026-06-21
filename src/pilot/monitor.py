"""
Pilot Monitoring — track pilot progress and metrics.

Provides tools for monitoring pilot usage, collecting feedback,
and generating reports.
"""

import json
from datetime import datetime, timezone
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class PilotMonitor:
    """
    Monitor pilot usage and collect metrics.
    """

    def __init__(self, branch_id: str = "branch_001") -> None:
        self._branch_id = branch_id
        self._usage_log: list[dict[str, Any]] = []
        self._feedback_log: list[dict[str, Any]] = []

    def log_usage(
        self,
        user_id: str,
        agent: str,
        query: str,
        response_time_ms: float,
        success: bool,
    ) -> None:
        """Log a usage event."""
        self._usage_log.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "branch_id": self._branch_id,
            "user_id": user_id,
            "agent": agent,
            "query": query[:200],
            "response_time_ms": response_time_ms,
            "success": success,
        })

    def log_feedback(
        self,
        user_id: str,
        rating: int,
        comment: str = "",
    ) -> None:
        """Log user feedback."""
        self._feedback_log.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "branch_id": self._branch_id,
            "user_id": user_id,
            "rating": rating,
            "comment": comment,
        })

    def get_usage_stats(self) -> dict[str, Any]:
        """Get usage statistics."""
        if not self._usage_log:
            return {"total_queries": 0}

        total = len(self._usage_log)
        successful = sum(1 for u in self._usage_log if u["success"])
        avg_response_time = sum(u["response_time_ms"] for u in self._usage_log) / total

        # Agent usage breakdown
        agent_counts: dict[str, int] = {}
        for u in self._usage_log:
            agent = u["agent"]
            agent_counts[agent] = agent_counts.get(agent, 0) + 1

        return {
            "branch_id": self._branch_id,
            "total_queries": total,
            "successful_queries": successful,
            "success_rate": successful / total,
            "avg_response_time_ms": round(avg_response_time, 2),
            "agent_usage": agent_counts,
        }

    def get_feedback_stats(self) -> dict[str, Any]:
        """Get feedback statistics."""
        if not self._feedback_log:
            return {"total_feedback": 0}

        total = len(self._feedback_log)
        avg_rating = sum(f["rating"] for f in self._feedback_log) / total

        return {
            "branch_id": self._branch_id,
            "total_feedback": total,
            "avg_rating": round(avg_rating, 2),
            "rating_distribution": self._get_rating_distribution(),
        }

    def _get_rating_distribution(self) -> dict[str, int]:
        """Get rating distribution."""
        dist: dict[str, int] = {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0}
        for f in self._feedback_log:
            rating = str(f["rating"])
            dist[rating] = dist.get(rating, 0) + 1
        return dist

    def generate_report(self) -> dict[str, Any]:
        """Generate pilot progress report."""
        usage = self.get_usage_stats()
        feedback = self.get_feedback_stats()

        return {
            "branch_id": self._branch_id,
            "report_date": datetime.now(timezone.utc).isoformat(),
            "usage": usage,
            "feedback": feedback,
            "summary": self._generate_summary(usage, feedback),
        }

    def _generate_summary(
        self,
        usage: dict[str, Any],
        feedback: dict[str, Any],
    ) -> str:
        """Generate human-readable summary."""
        parts = []

        if usage.get("total_queries", 0) > 0:
            parts.append(f"Total queries: {usage['total_queries']}")
            parts.append(f"Success rate: {usage['success_rate']:.1%}")
            parts.append(f"Avg response time: {usage['avg_response_time_ms']:.0f}ms")

        if feedback.get("total_feedback", 0) > 0:
            parts.append(f"User satisfaction: {feedback['avg_rating']:.1f}/5")

        return "\n".join(parts) if parts else "No data yet"

    def export_report(self, filepath: str) -> None:
        """Export report to JSON file."""
        report = self.generate_report()
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        logger.info("pilot.report_exported", filepath=filepath)


# Global pilot monitor
pilot_monitor = PilotMonitor()
