"""
Tests for metrics and observability modules.
"""

import pytest

from src.infrastructure.metrics import MetricsCollector
from src.infrastructure.observability import AgentMetrics


class TestMetricsCollector:
    """Test MetricsCollector functionality."""

    def setup_method(self):
        self.collector = MetricsCollector()

    def test_record_request(self):
        self.collector.record_request(
            agent="analytical",
            intent="analytics",
            latency_ms=150.0,
            success=True,
        )
        stats = self.collector.get_agent_stats("analytical")
        assert stats["total_requests"] == 1
        assert stats["successful"] == 1

    def test_record_failure(self):
        self.collector.record_request(
            agent="cx",
            intent="cx",
            latency_ms=200.0,
            success=False,
            error="timeout",
        )
        stats = self.collector.get_agent_stats("cx")
        assert stats["failed"] == 1

    def test_get_agent_stats_all(self):
        self.collector.record_request("analytical", "analytics", 100.0)
        self.collector.record_request("cx", "cx", 200.0)
        stats = self.collector.get_agent_stats()
        assert "analytical" in stats
        assert "cx" in stats

    def test_get_throughput(self):
        for _ in range(10):
            self.collector.record_request("analytical", "analytics", 100.0)
        throughput = self.collector.get_throughput(60)
        assert throughput["total_requests"] == 10

    def test_get_error_rate(self):
        self.collector.record_request("analytical", "analytics", 100.0, success=True)
        self.collector.record_request("cx", "cx", 200.0, success=False)
        error_rate = self.collector.get_error_rate(300)
        assert error_rate["total_errors"] == 1

    def test_get_latency_distribution(self):
        for i in range(10):
            self.collector.record_request("analytical", "analytics", float(i * 10))
        dist = self.collector.get_latency_distribution("analytical")
        assert dist["count"] == 10
        assert "p50" in dist
        assert "p95" in dist

    def test_get_dashboard_data(self):
        self.collector.record_request("analytical", "analytics", 100.0)
        data = self.collector.get_dashboard_data()
        assert "uptime_seconds" in data
        assert "total_requests" in data
        assert "agent_stats" in data

    def test_get_recent_errors(self):
        self.collector.record_request("cx", "cx", 100.0, success=False)
        errors = self.collector.get_recent_errors()
        assert len(errors) == 1


class TestAgentMetrics:
    """Test AgentMetrics functionality."""

    def setup_method(self):
        self.metrics = AgentMetrics()

    def test_record_request(self):
        self.metrics.record_request("analytical", 150.0, success=True)
        stats = self.metrics.stats
        assert stats["total_requests"] == 1
        assert stats["total_errors"] == 0

    def test_record_error(self):
        self.metrics.record_request("cx", 200.0, success=False)
        stats = self.metrics.stats
        assert stats["total_errors"] == 1
        assert stats["error_rate"] == 1.0

    def test_multiple_requests(self):
        for _ in range(5):
            self.metrics.record_request("analytical", 100.0)
        stats = self.metrics.stats
        assert stats["total_requests"] == 5
        assert stats["avg_latency_ms"] == 100.0

    def test_requests_by_agent(self):
        self.metrics.record_request("analytical", 100.0)
        self.metrics.record_request("cx", 200.0)
        self.metrics.record_request("analytical", 150.0)
        stats = self.metrics.stats
        assert stats["requests_by_agent"]["analytical"] == 2
        assert stats["requests_by_agent"]["cx"] == 1
