"""
Tests for the escalation workflow module.
"""

import pytest

from src.infrastructure.escalation.workflow import (
    EscalationWorkflow,
    EscalationLevel,
    EscalationReason,
)


class TestEscalationWorkflow:
    """Test EscalationWorkflow functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.workflow = EscalationWorkflow()

    def test_should_escalate_financial_decision(self):
        """Test escalation for financial decisions."""
        should, reason, level = self.workflow.should_escalate(
            user_query="أريد خصم 50% على الطلب",
            agent_response="",
            agent="analytical",
        )
        assert should is True
        assert reason == EscalationReason.FINANCIAL_DECISION
        assert level == EscalationLevel.HIGH

    def test_should_escalate_complaint(self):
        """Test escalation for sensitive complaints."""
        should, reason, level = self.workflow.should_escalate(
            user_query="لدي شكوى جدية من الخدمة",
            agent_response="",
            agent="cx",
        )
        assert should is True
        assert reason == EscalationReason.COMPLAINT_SENSITIVE
        assert level == EscalationLevel.HIGH

    def test_should_escalate_user_request(self):
        """Test escalation when user requests human."""
        should, reason, level = self.workflow.should_escalate(
            user_query="أحتاج التحدث مع مسؤول",
            agent_response="",
            agent="general",
        )
        assert should is True
        assert reason == EscalationReason.USER_REQUEST
        assert level == EscalationLevel.MEDIUM

    def test_should_not_escalate_normal_query(self):
        """Test no escalation for normal queries."""
        should, reason, level = self.workflow.should_escalate(
            user_query="ما هي مبيعات اليوم؟",
            agent_response="مبيعات اليوم 45,000 ريال",
            agent="analytical",
        )
        assert should is False
        assert reason is None

    def test_create_ticket(self):
        """Test ticket creation."""
        ticket = self.workflow.create_ticket(
            user_query="أريد خصم",
            agent_response="",
            reason=EscalationReason.FINANCIAL_DECISION,
            level=EscalationLevel.HIGH,
            user_id="user123",
            agent="analytical",
        )

        assert ticket.ticket_id.startswith("ESC-")
        assert ticket.reason == EscalationReason.FINANCIAL_DECISION
        assert ticket.level == EscalationLevel.HIGH
        assert ticket.assigned_to == "finance_team"
        assert ticket.resolved_at is None

    def test_resolve_ticket(self):
        """Test ticket resolution."""
        ticket = self.workflow.create_ticket(
            user_query="test",
            agent_response="",
            reason=EscalationReason.USER_REQUEST,
            level=EscalationLevel.LOW,
        )

        success = self.workflow.resolve_ticket(
            ticket_id=ticket.ticket_id,
            resolution="تم الحل",
            resolved_by="admin",
        )

        assert success is True
        assert ticket.resolved_at is not None
        assert ticket.resolution == "تم الحل"

    def test_get_pending_tickets(self):
        """Test getting pending tickets."""
        self.workflow.create_ticket(
            user_query="test1",
            agent_response="",
            reason=EscalationReason.USER_REQUEST,
            level=EscalationLevel.LOW,
        )
        self.workflow.create_ticket(
            user_query="test2",
            agent_response="",
            reason=EscalationReason.FINANCIAL_DECISION,
            level=EscalationLevel.HIGH,
        )

        pending = self.workflow.get_pending_tickets()
        assert len(pending) == 2

        # Resolve one
        self.workflow.resolve_ticket(
            ticket_id=pending[0].ticket_id,
            resolution="done",
            resolved_by="admin",
        )

        pending = self.workflow.get_pending_tickets()
        assert len(pending) == 1

    def test_get_ticket_stats(self):
        """Test ticket statistics."""
        self.workflow.create_ticket(
            user_query="test1",
            agent_response="",
            reason=EscalationReason.USER_REQUEST,
            level=EscalationLevel.LOW,
        )
        self.workflow.create_ticket(
            user_query="test2",
            agent_response="",
            reason=EscalationReason.FINANCIAL_DECISION,
            level=EscalationLevel.HIGH,
        )

        stats = self.workflow.get_ticket_stats()
        assert stats["total"] == 2
        assert stats["pending"] == 2
        assert stats["resolved"] == 0
        assert "low" in stats["by_level"]
        assert "high" in stats["by_level"]

    def test_get_escalation_message(self):
        """Test user-facing escalation message."""
        ticket = self.workflow.create_ticket(
            user_query="test",
            agent_response="",
            reason=EscalationReason.USER_REQUEST,
            level=EscalationLevel.MEDIUM,
        )

        message = self.workflow.get_escalation_message(ticket)
        assert ticket.ticket_id in message
        assert "تم تسجيل طلبك" in message

    def test_ticket_to_dict(self):
        """Test ticket serialization."""
        ticket = self.workflow.create_ticket(
            user_query="test",
            agent_response="response",
            reason=EscalationReason.COMPLEX_QUERY,
            level=EscalationLevel.LOW,
            user_id="user1",
            agent="analytical",
        )

        d = ticket.to_dict()
        assert d["ticket_id"] == ticket.ticket_id
        assert d["user_query"] == "test"
        assert d["reason"] == "complex_query"
        assert d["level"] == "low"
        assert d["user_id"] == "user1"
