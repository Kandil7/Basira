"""
Escalation module — human handoff workflow for agent requests.

Provides escalation rules, human assignment, and notification.
"""

from src.infrastructure.escalation.workflow import EscalationWorkflow, EscalationLevel

__all__ = ["EscalationWorkflow", "EscalationLevel"]
