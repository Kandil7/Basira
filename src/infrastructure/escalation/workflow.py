"""
Escalation workflow — human handoff for complex or sensitive requests.

Defines when to escalate to human agents, assignment logic, and notification.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class EscalationLevel(Enum):
    """Escalation priority levels."""
    LOW = "low"          # Non-urgent, can wait
    MEDIUM = "medium"    # Needs attention within hours
    HIGH = "high"        # Needs attention within 1 hour
    CRITICAL = "critical"  # Immediate attention required


class EscalationReason(Enum):
    """Reasons for escalation."""
    FINANCIAL_DECISION = "financial_decision"
    COMPLAINT_SENSITIVE = "complaint_sensitive"
    AGENT_UNCERTAINTY = "agent_uncertainty"
    USER_REQUEST = "user_request"
    GUARDRAIL_TRIGGERED = "guardrail_triggered"
    COMPLEX_QUERY = "complex_query"
    DATA_UNAVAILABLE = "data_unavailable"


class EscalationTicket:
    """An escalation ticket for human review."""

    def __init__(
        self,
        ticket_id: str,
        user_query: str,
        agent_response: str,
        reason: EscalationReason,
        level: EscalationLevel,
        user_id: str | None = None,
        session_id: str | None = None,
        agent: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.ticket_id = ticket_id
        self.user_query = user_query
        self.agent_response = agent_response
        self.reason = reason
        self.level = level
        self.user_id = user_id
        self.session_id = session_id
        self.agent = agent
        self.metadata = metadata or {}
        self.created_at = datetime.now(timezone.utc)
        self.assigned_to: str | None = None
        self.resolved_at: datetime.now(timezone.utc) | None = None
        self.resolution: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "ticket_id": self.ticket_id,
            "user_query": self.user_query,
            "agent_response": self.agent_response,
            "reason": self.reason.value,
            "level": self.level.value,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "agent": self.agent,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "assigned_to": self.assigned_to,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "resolution": self.resolution,
        }


class EscalationWorkflow:
    """
    Manages escalation of agent requests to human agents.

    Handles escalation rules, ticket creation, assignment, and tracking.
    """

    def __init__(self) -> None:
        self._tickets: dict[str, EscalationTicket] = {}
        self._ticket_counter = 0
        self._assignment_rules: dict[EscalationReason, str] = {
            EscalationReason.FINANCIAL_DECISION: "finance_team",
            EscalationReason.COMPLAINT_SENSITIVE: "customer_relations",
            EscalationReason.USER_REQUEST: "support_team",
            EscalationReason.GUARDRAIL_TRIGGERED: "admin_team",
            EscalationReason.COMPLEX_QUERY: "analytics_team",
            EscalationReason.DATA_UNAVAILABLE: "data_team",
            EscalationReason.AGENT_UNCERTAINTY: "support_team",
        }

    def should_escalate(
        self,
        user_query: str,
        agent_response: str,
        agent: str,
        context: dict[str, Any] | None = None,
    ) -> tuple[bool, EscalationReason | None, EscalationLevel]:
        """
        Determine if a request should be escalated to human.

        Args:
            user_query: Original user query
            agent_response: Agent's response
            agent: Which agent handled the query
            context: Additional context

        Returns:
            Tuple of (should_escalate, reason, level)
        """
        ctx = context or {}

        # Check for financial decision keywords
        financial_keywords = [
            "خصم", "discount", "إلغاء", "cancel", "استرجاع", "refund",
            "تعديل سعر", "price change", "موافقة", "approval",
        ]
        query_lower = user_query.lower()
        for kw in financial_keywords:
            if kw.lower() in query_lower:
                return True, EscalationReason.FINANCIAL_DECISION, EscalationLevel.HIGH

        # Check for sensitive complaint keywords
        complaint_keywords = [
            "شكوى", "complaint", "عدم رضا", "unsatisfied", "مشاكل جدية",
            "serious issues", "غرفة التجارية", "chamber of commerce",
        ]
        for kw in complaint_keywords:
            if kw.lower() in query_lower:
                return True, EscalationReason.COMPLAINT_SENSITIVE, EscalationLevel.HIGH

        # Check for explicit user request
        escalation_phrases = [
            "أحتاج مساعدة بشرية", "human help", "تحدث مع مسؤول",
            "speak to manager", "تصعيد", "escalate",
        ]
        for phrase in escalation_phrases:
            if phrase.lower() in query_lower:
                return True, EscalationReason.USER_REQUEST, EscalationLevel.MEDIUM

        # Check for guardrail trigger
        if ctx.get("guardrail_triggered"):
            return True, EscalationReason.GUARDRAIL_TRIGGERED, EscalationLevel.HIGH

        # Check for agent uncertainty
        if "لا أستطيع" in agent_response or "cannot" in agent_response.lower():
            return True, EscalationReason.AGENT_UNCERTAINTY, EscalationLevel.LOW

        # Check for complex query (very long or multi-part)
        if len(user_query) > 500 or user_query.count("؟") > 3:
            return True, EscalationReason.COMPLEX_QUERY, EscalationLevel.LOW

        return False, None, EscalationLevel.LOW

    def create_ticket(
        self,
        user_query: str,
        agent_response: str,
        reason: EscalationReason,
        level: EscalationLevel,
        user_id: str | None = None,
        session_id: str | None = None,
        agent: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> EscalationTicket:
        """Create an escalation ticket."""
        self._ticket_counter += 1
        ticket_id = f"ESC-{self._ticket_counter:06d}"

        ticket = EscalationTicket(
            ticket_id=ticket_id,
            user_query=user_query,
            agent_response=agent_response,
            reason=reason,
            level=level,
            user_id=user_id,
            session_id=session_id,
            agent=agent,
            metadata=metadata,
        )

        # Auto-assign based on rules
        team = self._assignment_rules.get(reason, "support_team")
        ticket.assigned_to = team

        self._tickets[ticket_id] = ticket

        logger.warning(
            "escalation.ticket_created",
            ticket_id=ticket_id,
            reason=reason.value,
            level=level.value,
            assigned_to=team,
            agent=agent,
        )

        return ticket

    def get_ticket(self, ticket_id: str) -> EscalationTicket | None:
        """Get a ticket by ID."""
        return self._tickets.get(ticket_id)

    def resolve_ticket(
        self,
        ticket_id: str,
        resolution: str,
        resolved_by: str,
    ) -> bool:
        """Resolve an escalation ticket."""
        ticket = self._tickets.get(ticket_id)
        if not ticket:
            return False

        ticket.resolution = resolution
        ticket.resolved_at = datetime.now(timezone.utc)
        ticket.assigned_to = resolved_by

        logger.info(
            "escalation.ticket_resolved",
            ticket_id=ticket_id,
            resolved_by=resolved_by,
        )
        return True

    def get_pending_tickets(self) -> list[EscalationTicket]:
        """Get all unresolved tickets."""
        return [
            t for t in self._tickets.values()
            if t.resolved_at is None
        ]

    def get_ticket_stats(self) -> dict[str, Any]:
        """Get escalation statistics."""
        total = len(self._tickets)
        resolved = sum(1 for t in self._tickets.values() if t.resolved_at)
        pending = total - resolved

        # By level
        by_level: dict[str, int] = {}
        for t in self._tickets.values():
            by_level[t.level.value] = by_level.get(t.level.value, 0) + 1

        # By reason
        by_reason: dict[str, int] = {}
        for t in self._tickets.values():
            by_reason[t.reason.value] = by_reason.get(t.reason.value, 0) + 1

        return {
            "total": total,
            "resolved": resolved,
            "pending": pending,
            "by_level": by_level,
            "by_reason": by_reason,
        }

    def get_escalation_message(self, ticket: EscalationTicket) -> str:
        """Generate a user-facing escalation message."""
        level_messages = {
            EscalationLevel.LOW: "تم تسجيل طلبك وسيتم معالجته قريباً",
            EscalationLevel.MEDIUM: "تم تسجيل طلبك وسيتم التواصل معك خلال ساعات",
            EscalationLevel.HIGH: "تم تسجيل طلبك بأولوية عالية وسيتم التواصل معك خلال ساعة",
            EscalationLevel.CRITICAL: "تم تسجيل طلبك بأولوية حرجة — جاري التواصل مع المسؤول فوراً",
        }

        return (
            f"📞 تم تصعيد طلبك (رقم التذكرة: {ticket.ticket_id})\n"
            f"{level_messages.get(ticket.level, '')}\n"
            f"السبب: {self._get_reason_arabic(ticket.reason)}"
        )

    @staticmethod
    def _get_reason_arabic(reason: EscalationReason) -> str:
        """Get Arabic description for escalation reason."""
        reasons = {
            EscalationReason.FINANCIAL_DECISION: "يحتاج قرار مالي",
            EscalationReason.COMPLAINT_SENSITIVE: "شكوى حساسة",
            EscalationReason.AGENT_UNCERTAINTY: "الوكيل غير متأكد",
            EscalationReason.USER_REQUEST: "طلب المستخدم",
            EscalationReason.GUARDRAIL_TRIGGERED: "مخالفة سياسة",
            EscalationReason.COMPLAINT_SENSITIVE: "سؤال معقد",
            EscalationReason.DATA_UNAVAILABLE: "بيانات غير متوفرة",
        }
        return reasons.get(reason, "سبب غير محدد")


# Global escalation workflow
escalation_workflow = EscalationWorkflow()
