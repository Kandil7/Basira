"""
PII Detection — detect and mask personally identifiable information.

Provides detection and masking of PII in logs, responses, and user input
for compliance and privacy protection.
"""

import re
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class PIIPattern:
    """A PII detection pattern."""

    def __init__(
        self,
        name: str,
        pattern: str,
        replacement: str = "***",
        description: str = "",
    ) -> None:
        self.name = name
        self.regex = re.compile(pattern)
        self.replacement = replacement
        self.description = description

    def detect(self, text: str) -> list[str]:
        """Detect matches in text."""
        return self.regex.findall(text)

    def mask(self, text: str) -> str:
        """Mask PII in text."""
        return self.regex.sub(self.replacement, text)


# Default PII patterns for Arabic and English
DEFAULT_PII_PATTERNS = [
    PIIPattern(
        name="phone_number",
        pattern=r"(?<!\d)(\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}(?!\d)|(?<!\d)\d{3}[-.\s]?\d{4}(?!\d)",
        replacement="[PHONE]",
        description="Phone numbers (international and local)",
    ),
    PIIPattern(
        name="email",
        pattern=r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
        replacement="[EMAIL]",
        description="Email addresses",
    ),
    PIIPattern(
        name="national_id",
        pattern=r"(?<!\d)\d{10}(?!\d)",
        replacement="[ID]",
        description="National ID numbers (10 digits)",
    ),
    PIIPattern(
        name="credit_card",
        pattern=r"(?<!\d)\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}(?!\d)",
        replacement="[CARD]",
        description="Credit card numbers",
    ),
    PIIPattern(
        name="iban",
        pattern=r"[A-Z]{2}\d{2}[A-Z0-9]{4,30}",
        replacement="[IBAN]",
        description="International Bank Account Numbers",
    ),
    PIIPattern(
        name="ip_address",
        pattern=r"(?<!\d)(\d{1,3}\.){3}\d{1,3}(?!\d)",
        replacement="[IP]",
        description="IPv4 addresses",
    ),
]


class PIIDetector:
    """
    PII detection and masking engine.

    Detects and masks personally identifiable information in text
    for privacy protection and compliance.
    """

    def __init__(
        self,
        custom_patterns: list[PIIPattern] | None = None,
        mask_replacement: str = "***",
    ) -> None:
        self._patterns = custom_patterns or DEFAULT_PII_PATTERNS
        self._mask_replacement = mask_replacement
        self._stats: dict[str, int] = {"detected": 0, "masked": 0}

    def detect(self, text: str) -> list[dict[str, Any]]:
        """
        Detect PII in text.

        Args:
            text: Text to scan

        Returns:
            List of detected PII with type and location.
        """
        detections = []

        for pattern in self._patterns:
            matches = pattern.detect(text)
            for match in matches:
                detections.append({
                    "type": pattern.name,
                    "value": match,
                    "description": pattern.description,
                })
                self._stats["detected"] += 1

        if detections:
            logger.info(
                "pii.detected",
                count=len(detections),
                types=[d["type"] for d in detections],
            )

        return detections

    def mask(self, text: str) -> str:
        """
        Mask PII in text.

        Args:
            text: Text to mask

        Returns:
            Text with PII replaced by placeholders.
        """
        masked = text

        for pattern in self._patterns:
            masked = pattern.mask(masked)

        if masked != text:
            self._stats["masked"] += 1

        return masked

    def detect_and_mask(self, text: str) -> tuple[str, list[dict[str, Any]]]:
        """
        Detect and mask PII in text.

        Args:
            text: Text to process

        Returns:
            Tuple of (masked_text, detections)
        """
        detections = self.detect(text)
        masked = self.mask(text)
        return masked, detections

    def scan_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Scan and mask PII in a dictionary.

        Args:
            data: Dictionary to scan

        Returns:
            Dictionary with PII masked in string values.
        """
        result = {}
        for key, value in data.items():
            if isinstance(value, str):
                result[key] = self.mask(value)
            elif isinstance(value, dict):
                result[key] = self.scan_dict(value)
            elif isinstance(value, list):
                result[key] = [
                    self.scan_dict(item) if isinstance(item, dict)
                    else self.mask(item) if isinstance(item, str)
                    else item
                    for item in value
                ]
            else:
                result[key] = value
        return result

    def get_stats(self) -> dict[str, Any]:
        """Get detection statistics."""
        return {
            **self._stats,
            "patterns_count": len(self._patterns),
        }


# Global PII detector
pii_detector = PIIDetector()
