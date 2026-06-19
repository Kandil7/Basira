"""
Unit tests for agent state.
"""

import pytest

from src.agents.state import AgentState, create_initial_state


class TestAgentState:
    """Tests for AgentState creation and schema."""

    def test_create_initial_state(self):
        """create_initial_state returns valid state."""
        state = create_initial_state("Hello world")
        assert state["messages"][0]["content"] == "Hello world"
        assert state["intent"] == "general"
        assert state["response"] == ""
        assert state["error"] is None

    def test_create_initial_state_with_metadata(self):
        """create_initial_state includes metadata."""
        metadata = {"channel": "whatsapp", "user_id": "U001"}
        state = create_initial_state("Test", metadata)
        assert state["metadata"]["channel"] == "whatsapp"
        assert state["metadata"]["user_id"] == "U001"

    def test_initial_state_empty_metadata(self):
        """create_initial_state uses empty dict for default metadata."""
        state = create_initial_state("Test")
        assert state["metadata"] == {}

    def test_initial_state_tools_used_empty(self):
        """create_initial_state starts with empty tools_used list."""
        state = create_initial_state("Test")
        assert state["tools_used"] == []
