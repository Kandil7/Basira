"""
Load testing utilities for Basira API.

Provides tools for testing API performance under concurrent load.
"""

import asyncio
import time
from typing import Any, Callable

import httpx
import structlog

logger = structlog.get_logger(__name__)


class LoadTester:
    """
    Load testing utility for API endpoints.

    Sends concurrent requests and measures performance metrics.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        api_key: str = "change-me-in-production",
    ) -> None:
        self._base_url = base_url
        self._api_key = api_key
        self._headers = {
            "Content-Type": "application/json",
            "X-Internal-Key": api_key,
        }

    async def test_endpoint(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        concurrent_requests: int = 10,
        duration_seconds: int = 30,
    ) -> dict[str, Any]:
        """
        Load test a single endpoint.

        Args:
            method: HTTP method
            path: API path
            payload: Request payload
            concurrent_requests: Number of concurrent requests
            duration_seconds: Test duration

        Returns:
            Performance metrics.
        """
        url = f"{self._base_url}{path}"
        results: list[dict[str, Any]] = []
        start_time = time.time()

        async def send_request():
            """Send a single request and record metrics."""
            request_start = time.time()
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    if method.upper() == "POST":
                        response = await client.post(
                            url,
                            json=payload,
                            headers=self._headers,
                        )
                    else:
                        response = await client.get(url, headers=self._headers)

                    latency = (time.time() - request_start) * 1000
                    results.append({
                        "status": response.status_code,
                        "latency_ms": latency,
                        "success": 200 <= response.status_code < 400,
                    })
            except Exception as e:
                latency = (time.time() - request_start) * 1000
                results.append({
                    "status": 0,
                    "latency_ms": latency,
                    "success": False,
                    "error": str(e),
                })

        # Run concurrent requests
        tasks = []
        for _ in range(concurrent_requests):
            tasks.append(send_request())

        await asyncio.gather(*tasks)

        total_time = time.time() - start_time

        # Calculate metrics
        latencies = [r["latency_ms"] for r in results]
        successes = sum(1 for r in results if r["success"])
        errors = len(results) - successes

        return {
            "endpoint": f"{method} {path}",
            "concurrent_requests": concurrent_requests,
            "total_requests": len(results),
            "total_time_seconds": round(total_time, 2),
            "requests_per_second": len(results) / total_time if total_time > 0 else 0,
            "success_rate": successes / len(results) if results else 0,
            "error_rate": errors / len(results) if results else 0,
            "latency": {
                "min": round(min(latencies), 2) if latencies else 0,
                "max": round(max(latencies), 2) if latencies else 0,
                "avg": round(sum(latencies) / len(latencies), 2) if latencies else 0,
                "p50": round(sorted(latencies)[len(latencies) // 2], 2) if latencies else 0,
                "p95": round(sorted(latencies)[int(len(latencies) * 0.95)], 2) if latencies else 0,
                "p99": round(sorted(latencies)[int(len(latencies) * 0.99)], 2) if latencies else 0,
            },
        }

    async def test_chat_endpoint(
        self,
        queries: list[str],
        concurrent_requests: int = 5,
    ) -> dict[str, Any]:
        """
        Load test the chat endpoint with multiple queries.

        Args:
            queries: List of test queries
            concurrent_requests: Concurrent requests per query

        Returns:
            Performance metrics.
        """
        all_results = []

        for query in queries:
            result = await self.test_endpoint(
                method="POST",
                path="/api/v1/chat",
                payload={"query": query, "channel": "load-test"},
                concurrent_requests=concurrent_requests,
            )
            all_results.append(result)

        # Aggregate results
        total_requests = sum(r["total_requests"] for r in all_results)
        total_successes = sum(
            int(r["success_rate"] * r["total_requests"]) for r in all_results
        )
        all_latencies = []
        for r in all_results:
            # Approximate latencies from stats
            avg = r["latency"]["avg"]
            count = r["total_requests"]
            all_latencies.extend([avg] * count)

        return {
            "test": "chat_endpoint",
            "queries_tested": len(queries),
            "total_requests": total_requests,
            "overall_success_rate": total_successes / total_requests if total_requests > 0 else 0,
            "overall_avg_latency_ms": round(sum(all_latencies) / len(all_latencies), 2) if all_latencies else 0,
            "per_query_results": all_results,
        }

    async def run_full_load_test(self) -> dict[str, Any]:
        """
        Run a comprehensive load test on all endpoints.

        Returns:
            Complete load test results.
        """
        logger.info("load_test.starting")

        results = {}

        # Test health endpoint (no auth)
        results["health"] = await self.test_endpoint(
            method="GET",
            path="/api/v1/health",
            concurrent_requests=20,
        )

        # Test chat endpoint
        results["chat"] = await self.test_chat_endpoint(
            queries=[
                "ما هي مبيعات اليوم؟",
                "أين طلبي رقم 123؟",
                "لخص التقارير",
                "ما هي أسعار المنتجات؟",
                "كم مخزون الصنف X؟",
            ],
            concurrent_requests=5,
        )

        # Test analytics endpoints
        results["daily_report"] = await self.test_endpoint(
            method="POST",
            path="/api/v1/reports/daily",
            payload={"date": "2025-01-15"},
            concurrent_requests=10,
        )

        # Test pricing endpoints
        results["pricing"] = await self.test_endpoint(
            method="POST",
            path="/api/v1/pricing/products",
            payload={"product_ids": []},
            concurrent_requests=10,
        )

        logger.info("load_test.completed", results=results.keys())

        return results


class PerformanceMonitor:
    """
    Real-time performance monitoring.

    Tracks API performance metrics over time.
    """

    def __init__(self) -> None:
        self._metrics: list[dict[str, Any]] = []
        self._start_time = time.time()

    def record_request(
        self,
        endpoint: str,
        method: str,
        status_code: int,
        latency_ms: float,
        success: bool,
    ) -> None:
        """Record a request metric."""
        self._metrics.append({
            "timestamp": time.time(),
            "endpoint": endpoint,
            "method": method,
            "status_code": status_code,
            "latency_ms": latency_ms,
            "success": success,
        })

    def get_stats(self, window_seconds: int = 300) -> dict[str, Any]:
        """
        Get performance statistics for a time window.

        Args:
            window_seconds: Time window in seconds

        Returns:
            Performance statistics.
        """
        cutoff = time.time() - window_seconds
        recent = [m for m in self._metrics if m["timestamp"] > cutoff]

        if not recent:
            return {"total_requests": 0}

        latencies = [m["latency_ms"] for m in recent]
        successes = sum(1 for m in recent if m["success"])

        return {
            "window_seconds": window_seconds,
            "total_requests": len(recent),
            "success_rate": successes / len(recent),
            "error_rate": 1 - (successes / len(recent)),
            "avg_latency_ms": round(sum(latencies) / len(latencies), 2),
            "min_latency_ms": round(min(latencies), 2),
            "max_latency_ms": round(max(latencies), 2),
            "p95_latency_ms": round(sorted(latencies)[int(len(latencies) * 0.95)], 2),
        }

    def get_endpoint_stats(self) -> dict[str, Any]:
        """Get stats broken down by endpoint."""
        endpoint_stats: dict[str, list] = {}

        for metric in self._metrics:
            endpoint = metric["endpoint"]
            if endpoint not in endpoint_stats:
                endpoint_stats[endpoint] = []
            endpoint_stats[endpoint].append(metric)

        result = {}
        for endpoint, metrics in endpoint_stats.items():
            latencies = [m["latency_ms"] for m in metrics]
            successes = sum(1 for m in metrics if m["success"])

            result[endpoint] = {
                "total_requests": len(metrics),
                "success_rate": successes / len(metrics),
                "avg_latency_ms": round(sum(latencies) / len(latencies), 2),
            }

        return result


# Global instances
load_tester = LoadTester()
performance_monitor = PerformanceMonitor()
