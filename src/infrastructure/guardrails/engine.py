"""
Guardrails engine — configurable safety rules, content filtering, and output validation.

Provides a framework for enforcing safety rules, filtering harmful content,
and validating agent outputs before returning to users.
"""

import re
from enum import Enum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class GuardrailAction(Enum):
    """Actions to take when a guardrail is triggered."""
    ALLOW = "allow"
    WARN = "warn"
    BLOCK = "block"
    REDACT = "redact"
    ESCALATE = "escalate"


class GuardrailRule:
    """A single guardrail rule."""

    def __init__(
        self,
        name: str,
        description: str,
        action: GuardrailAction = GuardrailAction.BLOCK,
        enabled: bool = True,
        priority: int = 0,
    ) -> None:
        self.name = name
        self.description = description
        self.action = action
        self.enabled = enabled
        self.priority = priority

    def check(self, text: str, context: dict[str, Any] | None = None) -> tuple[bool, str]:
        """
        Check if text violates this rule.

        Args:
            text: Text to check
            context: Additional context (agent, query, etc.)

        Returns:
            Tuple of (violated, reason)
        """
        raise NotImplementedError


class ContentFilterRule(GuardrailRule):
    """Rule that filters harmful or inappropriate content."""

    # Harmful content patterns (simplified for demo)
    HARMFUL_PATTERNS = [
        (r"(?i)\b(hack|exploit|attack)\b", "Potentially harmful technical content"),
        (r"(?i)\b(password|secret|api.?key)\b.*[=:]\s*\S", "Potential credential leak"),
    ]

    def check(self, text: str, context: dict[str, Any] | None = None) -> tuple[bool, str]:
        for pattern, reason in self.HARMFUL_PATTERNS:
            if re.search(pattern, text):
                return True, reason
        return False, ""


class FinancialGuardrailRule(GuardrailRule):
    """Rule that prevents unauthorized financial decisions."""

    FINANCIAL_KEYWORDS = [
        "خصم", "discount", "إلغاء طلب", "cancel order",
        "استرجاع مالي", "refund", "تعديل سعر", "price change",
    ]

    def check(self, text: str, context: dict[str, Any] | None = None) -> tuple[bool, str]:
        text_lower = text.lower()
        for keyword in self.FINANCIAL_KEYWORDS:
            if keyword.lower() in text_lower:
                return True, f"Financial decision detected: {keyword}"
        return False, ""


class OutputLengthRule(GuardrailRule):
    """Rule that limits response length."""

    def __init__(self, max_length: int = 5000, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.max_length = max_length

    def check(self, text: str, context: dict[str, Any] | None = None) -> tuple[bool, str]:
        if len(text) > self.max_length:
            return True, f"Response too long: {len(text)} > {self.max_length}"
        return False, ""


class LanguageConsistencyRule(GuardrailRule):
    """Rule that checks language consistency."""

    def check(self, text: str, context: dict[str, Any] | None = None) -> tuple[bool, str]:
        if not context:
            return False, ""

        query = context.get("query", "")
        if not query:
            return False, ""

        # Check if query is Arabic but response is not
        arabic_chars = sum(1 for c in query if '\u0600' <= c <= '\u06FF')
        if arabic_chars > len(query) * 0.3:
            response_arabic = sum(1 for c in text if '\u0600' <= c <= '\u06FF')
            if response_arabic < len(text) * 0.1:
                return True, "Language mismatch: Arabic query but non-Arabic response"

        return False, ""


class GuardrailsEngine:
    """
    Main guardrails engine that orchestrates rule checking.

    Manages a collection of guardrail rules and applies them
    to agent inputs and outputs.
    """

    def __init__(self, enabled: bool = True) -> None:
        self._enabled = enabled
        self._rules: list[GuardrailRule] = []
        self._stats: dict[str, int] = {"checked": 0, "violations": 0}

        # Register default rules
        self._register_defaults()

    def _register_defaults(self) -> None:
        """Register default guardrail rules."""
        self.add_rule(ContentFilterRule(
            name="content_filter",
            description="Filters harmful or inappropriate content",
            action=GuardrailAction.BLOCK,
            priority=100,
        ))
        self.add_rule(FinancialGuardrailRule(
            name="financial_guard",
            description="Prevents unauthorized financial decisions",
            action=GuardrailAction.ESCALATE,
            priority=90,
        ))
        self.add_rule(OutputLengthRule(
            name="output_length",
            description="Limits response length",
            action=GuardrailAction.REDACT,
            max_length=5000,
            priority=50,
        ))
        self.add_rule(LanguageConsistencyRule(
            name="language_check",
            description="Ensures language consistency",
            action=GuardrailAction.WARN,
            priority=30,
        ))

    def add_rule(self, rule: GuardrailRule) -> None:
        """Add a guardrail rule."""
        self._rules.append(rule)
        self._rules.sort(key=lambda r: r.priority, reverse=True)

    def remove_rule(self, name: str) -> bool:
        """Remove a guardrail rule by name."""
        for i, rule in enumerate(self._rules):
            if rule.name == name:
                del self._rules[i]
                return True
        return False

    async def check_input(self, text: str, context: dict[str, Any] | None = None) -> tuple[bool, str]:
        """
        Check user input against all rules.

        Args:
            text: User input text
            context: Additional context

        Returns:
            Tuple of (allowed, reason)
        """
        if not self._enabled:
            return True, ""

        self._stats["checked"] += 1

        for rule in self._rules:
            if not rule.enabled:
                continue

            violated, reason = rule.check(text, context)
            if violated:
                self._stats["violations"] += 1
                logger.warning(
                    "guardrail.input_violation",
                    rule=rule.name,
                    action=rule.action.value,
                    reason=reason,
                )

                if rule.action == GuardrailAction.BLOCK:
                    return False, f"Blocked by {rule.name}: {reason}"
                elif rule.action == GuardrailAction.ESCALATE:
                    return False, f"Requires human review ({rule.name}): {reason}"

        return True, ""

    async def check_output(
        self,
        text: str,
        agent: str,
        context: dict[str, Any] | None = None,
    ) -> tuple[bool, str, str]:
        """
        Check agent output against all rules.

        Args:
            text: Agent response text
            agent: Which agent produced the response
            context: Additional context (query, etc.)

        Returns:
            Tuple of (allowed, reason, filtered_text)
        """
        if not self._enabled:
            return True, "", text

        self._stats["checked"] += 1
        filtered_text = text

        for rule in self._rules:
            if not rule.enabled:
                continue

            check_context = {**(context or {}), "agent": agent}
            violated, reason = rule.check(filtered_text, check_context)

            if violated:
                self._stats["violations"] += 1
                logger.warning(
                    "guardrail.output_violation",
                    rule=rule.name,
                    agent=agent,
                    action=rule.action.value,
                    reason=reason,
                )

                if rule.action == GuardrailAction.BLOCK:
                    return False, f"Blocked by {rule.name}: {reason}", ""
                elif rule.action == GuardrailAction.REDACT:
                    # Truncate to max length (accounting for suffix)
                    if hasattr(rule, 'max_length'):
                        suffix = "\n\n[Content truncated by guardrails]"
                        max_content = rule.max_length - len(suffix)
                        filtered_text = filtered_text[:max_content] + suffix
                    return True, f"Redacted by {rule.name}: {reason}", filtered_text
                elif rule.action == GuardrailAction.WARN:
                    # Log warning and return reason
                    logger.warning("guardrail.warning", rule=rule.name, reason=reason)
                    return True, f"Warning ({rule.name}): {reason}", filtered_text

        return True, "", filtered_text

    def get_stats(self) -> dict[str, Any]:
        """Get guardrails statistics."""
        return {
            **self._stats,
            "rules_count": len(self._rules),
            "active_rules": sum(1 for r in self._rules if r.enabled),
            "violation_rate": (
                self._stats["violations"] / self._stats["checked"]
                if self._stats["checked"] > 0 else 0
            ),
        }

    def get_rules(self) -> list[dict[str, Any]]:
        """Get list of all rules."""
        return [
            {
                "name": rule.name,
                "description": rule.description,
                "action": rule.action.value,
                "enabled": rule.enabled,
                "priority": rule.priority,
            }
            for rule in self._rules
        ]


# Global guardrails engine
guardrails_engine = GuardrailsEngine()
