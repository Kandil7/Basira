"""
Escalation API routes.

Provides endpoints for human escalation, ticket management, and status tracking.
"""

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
import structlog

from src.infrastructure.escalation.workflow import (
    EscalationWorkflow,
    EscalationLevel,
    EscalationReason,
)

logger = structlog.get_logger(__name__)

router = APIRouter()


class EscalateRequest(BaseModel):
    """Request to escalate a query to human."""
    user_query: str = Field(..., description="Original user query")
    agent_response: str = Field(default="", description="Agent's response")
    agent: str = Field(default="unknown", description="Which agent handled this")
    user_id: str | None = Field(None, description="User ID")
    session_id: str | None = Field(None, description="Session ID")
    reason: str | None = Field(None, description="Override escalation reason")
    level: str | None = Field(None, description="Override escalation level")


class ResolveTicketRequest(BaseModel):
    """Request to resolve an escalation ticket."""
    resolution: str = Field(..., description="Resolution notes")
    resolved_by: str = Field(default="admin", description="Who resolved it")


@router.post("/escalate")
async def escalate_query(request: Request, body: EscalateRequest) -> dict[str, Any]:
    """
    Escalate a query to human agent.

    Automatically determines escalation reason and level based on query content,
    or uses provided overrides.
    """
    escalation = EscalationWorkflow()

    # Use overrides if provided
    if body.reason and body.level:
        try:
            reason = EscalationReason(body.reason)
            level = EscalationLevel(body.level)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid reason/level: {e}")
    else:
        # Auto-detect
        should_esc, auto_reason, auto_level = escalation.should_escalate(
            user_query=body.user_query,
            agent_response=body.agent_response,
            agent=body.agent,
        )
        reason = auto_reason or EscalationReason.USER_REQUEST
        level = auto_level

    # Create ticket
    ticket = escalation.create_ticket(
        user_query=body.user_query,
        agent_response=body.agent_response,
        reason=reason,
        level=level,
        user_id=body.user_id,
        session_id=body.session_id,
        agent=body.agent,
    )

    # Store ticket on app state
    if not hasattr(request.app.state, "escalation_tickets"):
        request.app.state.escalation_tickets = {}
    request.app.state.escalation_tickets[ticket.ticket_id] = ticket

    # Generate user message
    user_message = escalation.get_escalation_message(ticket)

    return {
        "ticket_id": ticket.ticket_id,
        "status": "escalated",
        "level": ticket.level.value,
        "reason": ticket.reason.value,
        "assigned_to": ticket.assigned_to,
        "message": user_message,
        "created_at": ticket.created_at.isoformat(),
    }


@router.get("/escalation/tickets")
async def list_tickets(request: Request) -> dict[str, Any]:
    """
    List all escalation tickets.
    """
    escalation = EscalationWorkflow()

    # Get tickets from app state
    tickets = getattr(request.app.state, "escalation_tickets", {})
    pending = [t for t in tickets.values() if t.resolved_at is None]
    resolved = [t for t in tickets.values() if t.resolved_at is not None]

    return {
        "total": len(tickets),
        "pending": len(pending),
        "resolved": len(resolved),
        "tickets": [t.to_dict() for t in tickets.values()],
    }


@router.get("/escalation/tickets/{ticket_id}")
async def get_ticket(request: Request, ticket_id: str) -> dict[str, Any]:
    """
    Get a specific escalation ticket.
    """
    tickets = getattr(request.app.state, "escalation_tickets", {})
    ticket = tickets.get(ticket_id)

    if not ticket:
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")

    return ticket.to_dict()


@router.post("/escalation/tickets/{ticket_id}/resolve")
async def resolve_ticket(
    request: Request,
    ticket_id: str,
    body: ResolveTicketRequest,
) -> dict[str, Any]:
    """
    Resolve an escalation ticket.
    """
    escalation = EscalationWorkflow()
    tickets = getattr(request.app.state, "escalation_tickets", {})
    ticket = tickets.get(ticket_id)

    if not ticket:
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")

    success = escalation.resolve_ticket(
        ticket_id=ticket_id,
        resolution=body.resolution,
        resolved_by=body.resolved_by,
    )

    if not success:
        raise HTTPException(status_code=500, detail="Failed to resolve ticket")

    return {
        "ticket_id": ticket_id,
        "status": "resolved",
        "resolution": body.resolution,
        "resolved_by": body.resolved_by,
        "resolved_at": ticket.resolved_at.isoformat(),
    }


@router.get("/escalation/stats")
async def escalation_stats(request: Request) -> dict[str, Any]:
    """
    Get escalation statistics.
    """
    tickets = getattr(request.app.state, "escalation_tickets", {})

    total = len(tickets)
    resolved = sum(1 for t in tickets.values() if t.resolved_at)
    pending = total - resolved

    # By level
    by_level: dict[str, int] = {}
    for t in tickets.values():
        by_level[t.level.value] = by_level.get(t.level.value, 0) + 1

    # By reason
    by_reason: dict[str, int] = {}
    for t in tickets.values():
        by_reason[t.reason.value] = by_reason.get(t.reason.value, 0) + 1

    return {
        "total": total,
        "resolved": resolved,
        "pending": pending,
        "by_level": by_level,
        "by_reason": by_reason,
    }
