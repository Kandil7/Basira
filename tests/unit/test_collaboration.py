"""
Tests for collaboration and delegation modules.
"""

import pytest
from unittest.mock import AsyncMock

from src.infrastructure.collaboration import (
    AgentDelegator,
    CollaborationRouter,
    DelegationRequest,
    DelegationReason,
)


class TestAgentDelegator:
    """Test AgentDelegator functionality."""

    def setup_method(self):
        self.delegator = AgentDelegator()

    def test_register_agent(self):
        handler = AsyncMock(return_value={"response": "test"})
        self.delegator.register_agent("analytical", handler)
        assert "analytical" in self.delegator._agent_handlers

    @pytest.mark.asyncio
    async def test_delegate_success(self):
        handler = AsyncMock(return_value={"response": "مبيعات اليوم 45,000"})
        self.delegator.register_agent("analytical", handler)

        request = DelegationRequest(
            from_agent="cx",
            to_agent="analytical",
            query="ما هي مبيعات اليوم؟",
            reason=DelegationReason.CROSS_DOMAIN,
        )
        result = await self.delegator.delegate(request)
        assert result["success"] is True
        assert "45,000" in result["response"]

    @pytest.mark.asyncio
    async def test_delegate_agent_not_found(self):
        request = DelegationRequest(
            from_agent="cx",
            to_agent="unknown",
            query="test",
            reason=DelegationReason.EXPERTISE_NEEDED,
        )
        result = await self.delegator.delegate(request)
        assert result["success"] is False
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_delegate_max_depth(self):
        handler = AsyncMock(return_value={"response": "test"})
        self.delegator.register_agent("agent1", handler)

        request = DelegationRequest(
            from_agent="cx",
            to_agent="agent1",
            query="test",
            reason=DelegationReason.CROSS_DOMAIN,
        )
        result = await self.delegator.delegate(request, depth=3)
        assert result["success"] is False
        assert "Maximum delegation depth" in result["error"]

    def test_get_stats(self):
        stats = self.delegator.get_stats()
        assert "total_delegations" in stats
        assert "registered_agents" in stats


class TestCollaborationRouter:
    """Test CollaborationRouter functionality."""

    def setup_method(self):
        self.router = CollaborationRouter()

    def test_analyze_query_single_agent(self):
        agents = self.router.analyze_query("مرحبا كيف حالك")
        # Simple greeting should not trigger cross-domain collaboration
        assert len(agents) <= 1

    def test_analyze_query_cross_domain(self):
        agents = self.router.analyze_query("سعر المبيعات والمخزون")
        assert len(agents) > 1

    def test_should_collaborate(self):
        assert self.router.should_collaborate("سعر المبيعات والمخزون") is True
        assert self.router.should_collaborate("مرحبا") is False

    @pytest.mark.asyncio
    async def test_collaborative_response_single(self):
        result = await self.router.collaborative_response(
            query="مرحبا",
            primary_agent="general",
            agent_handlers={},
        )
        assert result["collaboration"] is False


class TestDelegationRequest:
    """Test DelegationRequest dataclass."""

    def test_to_dict(self):
        request = DelegationRequest(
            from_agent="cx",
            to_agent="analytical",
            query="test query",
            reason=DelegationReason.CROSS_DOMAIN,
        )
        d = request.to_dict()
        assert d["from_agent"] == "cx"
        assert d["to_agent"] == "analytical"
        assert d["reason"] == "cross_domain"


class TestDelegationReason:
    """Test DelegationReason enum."""

    def test_values(self):
        assert DelegationReason.CROSS_DOMAIN.value == "cross_domain"
        assert DelegationReason.DATA_REQUIRED.value == "data_required"
        assert DelegationReason.EXPERTISE_NEEDED.value == "expertise_needed"
        assert DelegationReason.USER_REQUEST.value == "user_request"
