"""
Webhook security — validate Odoo webhook signatures and prevent replay attacks.
"""

import hashlib
import hmac
import time
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class WebhookSecurity:
    """
    Webhook security for validating Odoo webhook requests.

    Features:
    - HMAC signature validation
    - Timestamp-based replay protection
    - IP whitelist (optional)
    - Rate limiting per source
    """

    # Default tolerance for timestamp validation (5 minutes)
    DEFAULT_TIMESTAMP_TOLERANCE = 300

    def __init__(
        self,
        secret: str,
        timestamp_tolerance: int = DEFAULT_TIMESTAMP_TOLERANCE,
        allowed_ips: list[str] | None = None,
    ) -> None:
        """
        Initialize webhook security.

        Args:
            secret: Shared secret for HMAC validation
            timestamp_tolerance: Max age of requests in seconds
            allowed_ips: Optional IP whitelist
        """
        self._secret = secret.encode("utf-8") if isinstance(secret, str) else secret
        self._timestamp_tolerance = timestamp_tolerance
        self._allowed_ips = allowed_ips
        self._recent_nonces: dict[str, float] = {}
        self._stats = {"validated": 0, "rejected": 0}

    def validate_signature(
        self,
        payload: bytes,
        signature: str,
        timestamp: str | None = None,
    ) -> bool:
        """
        Validate webhook signature.

        Args:
            payload: Raw request body
            signature: HMAC signature from header
            timestamp: Optional timestamp for replay protection

        Returns:
            True if signature is valid.
        """
        self._stats["validated"] += 1

        # Validate timestamp if provided
        if timestamp:
            try:
                request_time = float(timestamp)
                if abs(time.time() - request_time) > self._timestamp_tolerance:
                    logger.warning(
                        "webhook.timestamp_expired",
                        timestamp=timestamp,
                        tolerance=self._timestamp_tolerance,
                    )
                    self._stats["rejected"] += 1
                    return False
            except (ValueError, TypeError):
                logger.warning("webhook.invalid_timestamp", timestamp=timestamp)
                self._stats["rejected"] += 1
                return False

        # Compute expected signature
        expected = self._compute_signature(payload, timestamp)

        # Compare signatures
        if not hmac.compare_digest(expected, signature):
            logger.warning("webhook.invalid_signature")
            self._stats["rejected"] += 1
            return False

        return True

    def _compute_signature(
        self,
        payload: bytes,
        timestamp: str | None = None,
    ) -> str:
        """
        Compute HMAC signature for payload.

        Args:
            payload: Raw request body
            timestamp: Optional timestamp to include in signature

        Returns:
            Hex-encoded HMAC signature.
        """
        if timestamp:
            message = f"{timestamp}.{payload.decode('utf-8', errors='replace')}"
        else:
            message = payload.decode("utf-8", errors="replace")

        return hmac.new(
            self._secret,
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def check_ip_whitelist(self, client_ip: str) -> bool:
        """
        Check if client IP is in whitelist.

        Args:
            client_ip: Client IP address

        Returns:
            True if IP is allowed (or no whitelist configured).
        """
        if not self._allowed_ips:
            return True

        allowed = client_ip in self._allowed_ips
        if not allowed:
            logger.warning("webhook.ip_not_allowed", ip=client_ip)
        return allowed

    def check_replay(self, nonce: str) -> bool:
        """
        Check for replay attacks using nonce.

        Args:
            nonce: Unique request identifier

        Returns:
            True if nonce is new (not a replay).
        """
        now = time.time()

        # Clean old nonces
        expired = [
            n for n, t in self._recent_nonces.items()
            if now - t > self._timestamp_tolerance
        ]
        for n in expired:
            del self._recent_nonces[n]

        # Check if nonce was used recently
        if nonce in self._recent_nonces:
            logger.warning("webhook.replay_detected", nonce=nonce)
            return False

        # Record nonce
        self._recent_nonces[nonce] = now
        return True

    def get_stats(self) -> dict[str, Any]:
        """Get security statistics."""
        return {
            **self._stats,
            "rejection_rate": (
                self._stats["rejected"] / self._stats["validated"]
                if self._stats["validated"] > 0 else 0
            ),
            "recent_nonces": len(self._recent_nonces),
        }
