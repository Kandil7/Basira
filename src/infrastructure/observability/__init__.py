"""
Observability module — OpenTelemetry tracing and metrics.

Provides distributed tracing, metrics collection, and structured logging
for production monitoring of the Basira AI platform.
"""

from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# Module-level state
_tracer = None
_meter = None


def init_telemetry(
    service_name: str = "basira-api",
    enabled: bool = True,
) -> None:
    """
    Initialize OpenTelemetry tracing and metrics.

    Args:
        service_name: Name of the service for tracing
        enabled: Whether telemetry is enabled
    """
    global _tracer, _meter

    if not enabled:
        logger.info("telemetry.disabled")
        return

    try:
        from opentelemetry import trace, metrics
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.resources import Resource

        resource = Resource.create({"service.name": service_name})

        # Tracing
        provider = TracerProvider(resource=resource)
        trace.set_tracer_provider(provider)
        _tracer = trace.get_tracer(service_name)

        # Metrics
        meter_provider = MeterProvider(resource=resource)
        metrics.set_meter_provider(meter_provider)
        _meter = metrics.get_meter(service_name)

        logger.info("telemetry.initialized", service=service_name)

    except ImportError:
        logger.warning("telemetry.missing_dep", dep="opentelemetry")
    except Exception as e:
        logger.error("telemetry.init_failed", error=str(e))


def get_tracer() -> Any:
    """Get the global tracer instance."""
    return _tracer


def get_meter() -> Any:
    """Get the global meter instance."""
    return _meter


class AgentMetrics:
    """
    Pre-defined metrics for agent monitoring.

    Tracks request counts, latency, and error rates per agent.
    """

    def __init__(self) -> None:
        self._request_count = 0
        self._error_count = 0
        self._total_latency_ms = 0.0
        self._agent_counts: dict[str, int] = {}

    def record_request(
        self,
        agent: str,
        latency_ms: float,
        success: bool = True,
    ) -> None:
        """Record a request metric."""
        self._request_count += 1
        self._total_latency_ms += latency_ms
        self._agent_counts[agent] = self._agent_counts.get(agent, 0) + 1

        if not success:
            self._error_count += 1

    @property
    def stats(self) -> dict[str, Any]:
        """Get current metrics stats."""
        avg_latency = (
            self._total_latency_ms / self._request_count
            if self._request_count > 0
            else 0
        )
        return {
            "total_requests": self._request_count,
            "total_errors": self._error_count,
            "error_rate": self._error_count / self._request_count if self._request_count > 0 else 0,
            "avg_latency_ms": round(avg_latency, 2),
            "requests_by_agent": self._agent_counts.copy(),
        }


# Global metrics instance
agent_metrics = AgentMetrics()
