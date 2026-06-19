"""
Circuit breaker pattern for external service calls.

Provides fault tolerance for Odoo, Qdrant, and LLM API calls.
When failures exceed a threshold, the circuit opens and rejects calls
until a recovery timeout expires.
"""

import time
from enum import Enum

import structlog

logger = structlog.get_logger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation — calls pass through
    OPEN = "open"  # Failing — calls are rejected
    HALF_OPEN = "half_open"  # Testing — one call allowed through


class CircuitBreaker:
    """
    Simple circuit breaker for external service protection.

    Args:
        failure_threshold: Number of consecutive failures before opening
        recovery_timeout: Seconds to wait before trying again
        name: Identifier for logging
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        name: str = "default",
    ) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.name = name
        self.failure_count = 0
        self.last_failure_time: float = 0.0
        self.state = CircuitState.CLOSED

    def can_execute(self) -> bool:
        """Check if a call is allowed through the circuit."""
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            elapsed = time.time() - self.last_failure_time
            if elapsed > self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                logger.info(
                    "circuit_breaker.half_open",
                    name=self.name,
                    elapsed=round(elapsed, 1),
                )
                return True
            return False

        # HALF_OPEN: allow one attempt
        return True

    def record_success(self) -> None:
        """Record a successful call — reset the circuit."""
        if self.state == CircuitState.HALF_OPEN:
            logger.info("circuit_breaker.closed", name=self.name, reason="half_open_success")
        self.failure_count = 0
        self.state = CircuitState.CLOSED

    def record_failure(self) -> None:
        """Record a failed call — may trip the circuit open."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning(
                "circuit_breaker.opened",
                name=self.name,
                failure_count=self.failure_count,
                recovery_timeout=self.recovery_timeout,
            )

    @property
    def stats(self) -> dict:
        """Return current circuit breaker stats."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
        }
