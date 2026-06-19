"""
Real-time metrics — live agent performance, latency, and error rate monitoring.

Provides metrics collection, aggregation, and exposure for dashboards.
"""

import time
from collections import deque
from datetime import datetime, timezone
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class MetricsCollector:
    """
    In-memory metrics collector for real-time monitoring.

    Collects and aggregates metrics for agent performance,
    latency, error rates, and throughput.
    """

    def __init__(self, max_history: int = 10000) -> None:
        self._max_history = max_history
        self._requests: deque = deque(maxlen=max_history)
        self._agent_metrics: dict[str, dict] = {}
        self._start_time = time.time()

    def record_request(
        self,
        agent: str,
        intent: str,
        latency_ms: float,
        success: bool = True,
        tools_used: list[str] | None = None,
        error: str | None = None,
    ) -> None:
        """
        Record a request metric.

        Args:
            agent: Agent that handled the request
            intent: Classified intent
            latency_ms: Processing time in milliseconds
            success: Whether the request was successful
            tools_used: Tools invoked during processing
            error: Error message if failed
        """
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": agent,
            "intent": intent,
            "latency_ms": latency_ms,
            "success": success,
            "tools_used": tools_used or [],
            "error": error,
        }

        self._requests.append(record)

        # Update agent-specific metrics
        if agent not in self._agent_metrics:
            self._agent_metrics[agent] = {
                "total": 0,
                "success": 0,
                "failed": 0,
                "total_latency_ms": 0.0,
                "latencies": deque(maxlen=1000),
            }

        metrics = self._agent_metrics[agent]
        metrics["total"] += 1
        metrics["total_latency_ms"] += latency_ms
        metrics["latencies"].append(latency_ms)

        if success:
            metrics["success"] += 1
        else:
            metrics["failed"] += 1

    def get_agent_stats(self, agent: str | None = None) -> dict[str, Any]:
        """
        Get statistics for agents.

        Args:
            agent: Specific agent to get stats for (None for all)

        Returns:
            Statistics dictionary.
        """
        if agent:
            metrics = self._agent_metrics.get(agent)
            if not metrics:
                return {}
            return self._calculate_agent_stats(agent, metrics)

        # All agents
        stats = {}
        for agent_name, metrics in self._agent_metrics.items():
            stats[agent_name] = self._calculate_agent_stats(agent_name, metrics)
        return stats

    def _calculate_agent_stats(self, agent: str, metrics: dict) -> dict[str, Any]:
        """Calculate stats for a single agent."""
        latencies = list(metrics["latencies"])
        avg_latency = sum(latencies) / len(latencies) if latencies else 0
        p95_latency = sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0
        p99_latency = sorted(latencies)[int(len(latencies) * 0.99)] if latencies else 0

        return {
            "agent": agent,
            "total_requests": metrics["total"],
            "successful": metrics["success"],
            "failed": metrics["failed"],
            "success_rate": metrics["success"] / metrics["total"] if metrics["total"] > 0 else 0,
            "avg_latency_ms": round(avg_latency, 2),
            "p95_latency_ms": round(p95_latency, 2),
            "p99_latency_ms": round(p99_latency, 2),
        }

    def get_throughput(self, window_seconds: int = 60) -> dict[str, Any]:
        """
        Get request throughput over a time window.

        Args:
            window_seconds: Time window in seconds

        Returns:
            Throughput statistics.
        """
        now = time.time()
        cutoff = now - window_seconds

        recent = [
            r for r in self._requests
            if datetime.fromisoformat(r["timestamp"]).timestamp() > cutoff
        ]

        total = len(recent)
        by_agent = {}
        for r in recent:
            agent = r["agent"]
            by_agent[agent] = by_agent.get(agent, 0) + 1

        return {
            "window_seconds": window_seconds,
            "total_requests": total,
            "requests_per_second": total / window_seconds if window_seconds > 0 else 0,
            "by_agent": by_agent,
        }

    def get_error_rate(self, window_seconds: int = 300) -> dict[str, Any]:
        """
        Get error rate over a time window.

        Args:
            window_seconds: Time window in seconds

        Returns:
            Error rate statistics.
        """
        now = time.time()
        cutoff = now - window_seconds

        recent = [
            r for r in self._requests
            if datetime.fromisoformat(r["timestamp"]).timestamp() > cutoff
        ]

        total = len(recent)
        errors = sum(1 for r in recent if not r["success"])

        # Error breakdown by agent
        error_by_agent = {}
        for r in recent:
            if not r["success"]:
                agent = r["agent"]
                error_by_agent[agent] = error_by_agent.get(agent, 0) + 1

        return {
            "window_seconds": window_seconds,
            "total_requests": total,
            "total_errors": errors,
            "error_rate": errors / total if total > 0 else 0,
            "errors_by_agent": error_by_agent,
        }

    def get_recent_errors(self, limit: int = 20) -> list[dict[str, Any]]:
        """
        Get recent error records.

        Args:
            limit: Maximum errors to return

        Returns:
            List of error records.
        """
        errors = [
            r for r in self._requests
            if not r["success"]
        ]
        return errors[-limit:]

    def get_latency_distribution(self, agent: str | None = None) -> dict[str, Any]:
        """
        Get latency distribution.

        Args:
            agent: Specific agent (None for all)

        Returns:
            Latency distribution with percentiles.
        """
        if agent:
            metrics = self._agent_metrics.get(agent)
            if not metrics:
                return {}
            latencies = list(metrics["latencies"])
        else:
            latencies = [r["latency_ms"] for r in self._requests]

        if not latencies:
            return {"count": 0}

        sorted_latencies = sorted(latencies)
        count = len(sorted_latencies)

        return {
            "count": count,
            "min": round(sorted_latencies[0], 2),
            "max": round(sorted_latencies[-1], 2),
            "avg": round(sum(sorted_latencies) / count, 2),
            "p50": round(sorted_latencies[int(count * 0.5)], 2),
            "p75": round(sorted_latencies[int(count * 0.75)], 2),
            "p90": round(sorted_latencies[int(count * 0.9)], 2),
            "p95": round(sorted_latencies[int(count * 0.95)], 2),
            "p99": round(sorted_latencies[int(count * 0.99)], 2),
        }

    def get_dashboard_data(self) -> dict[str, Any]:
        """
        Get all data needed for the dashboard.

        Returns:
            Complete dashboard data.
        """
        uptime = time.time() - self._start_time

        return {
            "uptime_seconds": round(uptime, 0),
            "uptime_human": self._format_uptime(uptime),
            "total_requests": len(self._requests),
            "throughput": self.get_throughput(60),
            "error_rate": self.get_error_rate(300),
            "agent_stats": self.get_agent_stats(),
            "latency": self.get_latency_distribution(),
            "recent_errors": self.get_recent_errors(5),
        }

    @staticmethod
    def _format_uptime(seconds: float) -> str:
        """Format uptime as human-readable string."""
        days = int(seconds // 86400)
        hours = int((seconds % 86400) // 3600)
        minutes = int((seconds % 3600) // 60)

        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        parts.append(f"{minutes}m")

        return " ".join(parts)


# Global metrics instance
metrics_collector = MetricsCollector()
