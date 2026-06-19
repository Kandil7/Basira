"""
Sprint 4 tests — Guardrails, RBAC, and PII Detection.

Tests the guardrails engine, RBAC middleware, and PII detector
with mocked dependencies (no real LLM or database calls).
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.infrastructure.guardrails.engine import (
    GuardrailsEngine,
    GuardrailAction,
    GuardrailRule,
    ContentFilterRule,
    FinancialGuardrailRule,
    OutputLengthRule,
    LanguageConsistencyRule,
)
from src.infrastructure.guardrails.pii import (
    PIIDetector,
    PIIPattern,
)
from src.infrastructure.rbac import (
    Role,
    Permission,
    User,
    RBACMiddleware,
    rbac,
    ROLE_PERMISSIONS,
)


# ── Guardrails Engine Tests ──────────────────────────────────────────

class TestGuardrailsEngine:
    """Test GuardrailsEngine functionality."""

    def test_engine_initialization(self):
        """Test engine initializes with default rules."""
        engine = GuardrailsEngine()
        assert engine._enabled is True
        assert len(engine._rules) == 4  # 4 default rules

    def test_engine_disabled(self):
        """Test engine returns allowed when disabled."""
        engine = GuardrailsEngine(enabled=False)
        import asyncio
        allowed, reason = asyncio.get_event_loop().run_until_complete(
            engine.check_input("test", {})
        )
        assert allowed is True
        assert reason == ""

    def test_content_filter_blocks_harmful(self):
        """Test content filter blocks harmful patterns."""
        engine = GuardrailsEngine()
        import asyncio
        allowed, reason = asyncio.get_event_loop().run_until_complete(
            engine.check_input("hack the system", {})
        )
        assert allowed is False
        assert "content_filter" in reason

    def test_content_filter_allows_safe(self):
        """Test content filter allows safe content."""
        engine = GuardrailsEngine()
        import asyncio
        allowed, reason = asyncio.get_event_loop().run_until_complete(
            engine.check_input("What are today's sales?", {})
        )
        assert allowed is True

    def test_financial_guard_escalates(self):
        """Test financial guard escalates financial decisions."""
        engine = GuardrailsEngine()
        import asyncio
        allowed, reason = asyncio.get_event_loop().run_until_complete(
            engine.check_input("خصم 20% على المنتج", {})
        )
        assert allowed is False
        assert "financial_guard" in reason

    def test_output_length_truncates(self):
        """Test output length truncates long responses."""
        engine = GuardrailsEngine()
        import asyncio
        long_text = "x" * 6000
        allowed, reason, filtered = asyncio.get_event_loop().run_until_complete(
            engine.check_output(long_text, "test_agent", {})
        )
        assert allowed is True
        assert len(filtered) <= 5000

    def test_language_check_warns(self):
        """Test language check warns on mismatch."""
        engine = GuardrailsEngine()
        import asyncio
        allowed, reason, filtered = asyncio.get_event_loop().run_until_complete(
            engine.check_output("Hello, how can I help you?", "test_agent", {"query": "ما هي مبيعات اليوم؟"})
        )
        assert allowed is True  # WARN doesn't block
        assert "language_check" in reason

    def test_add_remove_rule(self):
        """Test adding and removing custom rules."""
        engine = GuardrailsEngine()

        class CustomRule(GuardrailRule):
            def check(self, text, context=None):
                return False, ""

        rule = CustomRule(name="custom", description="Custom rule", priority=10)
        engine.add_rule(rule)
        assert len(engine._rules) == 5

        engine.remove_rule("custom")
        assert len(engine._rules) == 4

    def test_get_stats(self):
        """Test statistics collection."""
        engine = GuardrailsEngine()
        stats = engine.get_stats()
        assert "checked" in stats
        assert "violations" in stats
        assert "rules_count" in stats


# ── PII Detection Tests ──────────────────────────────────────────────

class TestPIIDetector:
    """Test PIIDetector functionality."""

    def test_detector_initialization(self):
        """Test detector initializes with default patterns."""
        detector = PIIDetector()
        assert len(detector._patterns) == 6  # 6 default patterns

    def test_detect_phone_number(self):
        """Test phone number detection."""
        detector = PIIDetector()
        detections = detector.detect("Call me at +1-234-567-8900")
        assert any(d["type"] == "phone_number" for d in detections)

    def test_detect_email(self):
        """Test email detection."""
        detector = PIIDetector()
        detections = detector.detect("Email me at user@example.com")
        assert any(d["type"] == "email" for d in detections)

    def test_detect_national_id(self):
        """Test national ID detection."""
        detector = PIIDetector()
        detections = detector.detect("ID: 1234567890")
        assert any(d["type"] == "national_id" for d in detections)

    def test_detect_credit_card(self):
        """Test credit card detection."""
        detector = PIIDetector()
        detections = detector.detect("Card: 4111-1111-1111-1111")
        assert any(d["type"] == "credit_card" for d in detections)

    def test_detect_iban(self):
        """Test IBAN detection."""
        detector = PIIDetector()
        detections = detector.detect("IBAN: DE89370400440532013000")
        assert any(d["type"] == "iban" for d in detections)

    def test_detect_ip_address(self):
        """Test IP address detection."""
        detector = PIIDetector()
        detections = detector.detect("Server: 192.168.1.1")
        assert any(d["type"] == "ip_address" for d in detections)

    def test_mask_pii(self):
        """Test PII masking."""
        detector = PIIDetector()
        masked = detector.mask("Email: user@example.com, Phone: +1-234-567-8900")
        assert "[EMAIL]" in masked
        assert "[PHONE]" in masked
        assert "user@example.com" not in masked

    def test_detect_and_mask(self):
        """Test combined detect and mask."""
        detector = PIIDetector()
        masked, detections = detector.detect_and_mask("Send to john@test.com")
        assert "[EMAIL]" in masked
        assert len(detections) > 0

    def test_scan_dict(self):
        """Test scanning dictionary for PII."""
        detector = PIIDetector()
        data = {
            "name": "John",
            "email": "john@test.com",
            "nested": {"phone": "+1-234-567-8900"},
            "list": ["call 555-1234"],
        }
        result = detector.scan_dict(data)
        assert result["name"] == "John"
        assert "[EMAIL]" in result["email"]
        assert "[PHONE]" in result["nested"]["phone"]
        assert "[PHONE]" in result["list"][0]

    def test_get_stats(self):
        """Test statistics collection."""
        detector = PIIDetector()
        detector.detect("test@example.com")
        stats = detector.get_stats()
        assert "detected" in stats
        assert "masked" in stats


# ── RBAC Tests ───────────────────────────────────────────────────────

class TestRBAC:
    """Test RBAC functionality."""

    def test_role_enum(self):
        """Test role enum values."""
        assert Role.ADMIN.value == "admin"
        assert Role.MANAGER.value == "manager"
        assert Role.ANALYST.value == "analyst"
        assert Role.OPERATOR.value == "operator"
        assert Role.VIEWER.value == "viewer"
        assert Role.API.value == "api"

    def test_permission_enum(self):
        """Test permission enum values."""
        assert Permission.CHAT.value == "chat"
        assert Permission.ANALYTICS_READ.value == "analytics:read"
        assert Permission.ADMIN.value == "admin"

    def test_user_initialization(self):
        """Test user creation."""
        user = User("test_user", Role.ANALYST, "Test User")
        assert user.user_id == "test_user"
        assert user.role == Role.ANALYST
        assert user.name == "Test User"

    def test_user_permissions(self):
        """Test user permissions based on role."""
        admin = User("admin", Role.ADMIN)
        analyst = User("analyst", Role.ANALYST)

        assert admin.has_permission(Permission.ADMIN)
        assert admin.has_permission(Permission.ANALYTICS_READ)
        assert analyst.has_permission(Permission.ANALYTICS_READ)
        assert not analyst.has_permission(Permission.ADMIN)

    def test_user_extra_permissions(self):
        """Test user extra permissions."""
        user = User("test", Role.VIEWER, extra_permissions={Permission.CHAT})
        assert user.has_permission(Permission.CHAT)
        assert not user.has_permission(Permission.ANALYTICS_READ)

    def test_rbac_middleware_initialization(self):
        """Test RBAC middleware initialization."""
        middleware = RBACMiddleware()
        assert len(middleware._users) == 6  # 6 default users

    def test_rbac_default_users(self):
        """Test default users are registered."""
        assert rbac.get_user("admin") is not None
        assert rbac.get_user("manager") is not None
        assert rbac.get_user("analyst") is not None
        assert rbac.get_user("operator") is not None
        assert rbac.get_user("viewer") is not None
        assert rbac.get_user("n8n") is not None

    def test_rbac_endpoint_registration(self):
        """Test endpoint permission registration."""
        middleware = RBACMiddleware()
        middleware.register_endpoint("/test", "POST", [Permission.CHAT])
        assert "POST:/test" in middleware._endpoint_permissions

    def test_rbac_admin_bypass(self):
        """Test admin bypasses all checks."""
        admin = rbac.get_user("admin")
        assert rbac.check_endpoint_access(admin, "/api/v1/chat", "POST")
        assert rbac.check_endpoint_access(admin, "/api/v1/reports/daily", "POST")
        assert rbac.check_endpoint_access(admin, "/api/v1/pricing/products", "POST")

    def test_rbac_viewer_limited(self):
        """Test viewer has limited access."""
        viewer = rbac.get_user("viewer")
        assert rbac.check_endpoint_access(viewer, "/api/v1/chat", "POST")
        assert not rbac.check_endpoint_access(viewer, "/api/v1/reports/daily", "POST")

    def test_rbac_api_role(self):
        """Test API role access."""
        n8n = rbac.get_user("n8n")
        assert rbac.check_endpoint_access(n8n, "/api/v1/chat", "POST")
        assert rbac.check_endpoint_access(n8n, "/api/v1/internal/search", "POST")
        assert not rbac.check_endpoint_access(n8n, "/api/v1/reports/daily", "POST")

    def test_get_user_permissions(self):
        """Test getting user permissions."""
        permissions = rbac.get_user_permissions("analyst")
        assert "chat" in permissions
        assert "analytics:read" in permissions

    def test_get_stats(self):
        """Test RBAC statistics."""
        stats = rbac.get_stats()
        assert stats["total_users"] == 6
        assert "admin" in stats["roles"]


# ── ContentFilterRule Tests ──────────────────────────────────────────

class TestContentFilterRule:
    """Test ContentFilterRule specifically."""

    def test_blocks_hack_keyword(self):
        """Test blocks hack keyword."""
        rule = ContentFilterRule(name="test", description="test")
        violated, reason = rule.check("hack the system")
        assert violated is True

    def test_blocks_credential_leak(self):
        """Test blocks potential credential leak."""
        rule = ContentFilterRule(name="test", description="test")
        violated, reason = rule.check("password: secret123")
        assert violated is True

    def test_allows_safe_content(self):
        """Test allows safe content."""
        rule = ContentFilterRule(name="test", description="test")
        violated, reason = rule.check("What are today's sales?")
        assert violated is False


# ── FinancialGuardrailRule Tests ─────────────────────────────────────

class TestFinancialGuardrailRule:
    """Test FinancialGuardrailRule specifically."""

    def test_blocks_arabic_discount(self):
        """Test blocks Arabic discount keyword."""
        rule = FinancialGuardrailRule(name="test", description="test")
        violated, reason = rule.check("خصم 20%")
        assert violated is True

    def test_blocks_english_refund(self):
        """Test blocks English refund keyword."""
        rule = FinancialGuardrailRule(name="test", description="test")
        violated, reason = rule.check("Process refund for order")
        assert violated is True

    def test_allows_safe_content(self):
        """Test allows safe content."""
        rule = FinancialGuardrailRule(name="test", description="test")
        violated, reason = rule.check("What are today's sales?")
        assert violated is False
