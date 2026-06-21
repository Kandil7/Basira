"""
Tests for memory and context modules.
"""

import pytest

from src.infrastructure.memory import ConversationMemory, ContextBuilder
from src.infrastructure.agent_context import AgentContextManager


class TestConversationMemory:
    """Test ConversationMemory functionality."""

    def setup_method(self):
        self.memory = ConversationMemory()

    @pytest.mark.asyncio
    async def test_add_message(self):
        await self.memory.add_message(
            session_id="s1",
            user_id="u1",
            role="user",
            content="مرحبا",
        )
        history = await self.memory.get_history("s1", user_id="u1")
        assert len(history) == 1
        assert history[0]["content"] == "مرحبا"

    @pytest.mark.asyncio
    async def test_get_history(self):
        for i in range(5):
            await self.memory.add_message(
                session_id="s1",
                user_id="u1",
                role="user",
                content=f"message {i}",
            )
        history = await self.memory.get_history("s1", user_id="u1", limit=3)
        assert len(history) == 3

    @pytest.mark.asyncio
    async def test_get_user_context(self):
        await self.memory.add_message(
            session_id="s1",
            user_id="u1",
            role="user",
            content="test",
            agent="analytical",
        )
        context = await self.memory.get_user_context("u1")
        assert context["total_messages"] == 1
        assert "analytical" in context["agent_usage"]

    @pytest.mark.asyncio
    async def test_update_preferences(self):
        await self.memory.update_preferences("u1", {"language": "ar"})
        pref = await self.memory.get_preference("u1", "language")
        assert pref == "ar"

    @pytest.mark.asyncio
    async def test_search_memory(self):
        await self.memory.add_message(
            session_id="s1",
            user_id="u1",
            role="user",
            content="مبيعات اليوم",
        )
        results = await self.memory.search_memory("مبيعات")
        assert len(results) > 0

    @pytest.mark.asyncio
    async def test_clear_history(self):
        await self.memory.add_message(
            session_id="s1",
            user_id="u1",
            role="user",
            content="test",
        )
        count = await self.memory.clear_history(user_id="u1")
        assert count == 1

    def test_get_stats(self):
        stats = self.memory.get_stats()
        assert "total_sessions" in stats
        assert "total_messages" in stats


class TestContextBuilder:
    """Test ContextBuilder functionality."""

    def setup_method(self):
        self.memory = ConversationMemory()
        self.builder = ContextBuilder(self.memory)

    @pytest.mark.asyncio
    async def test_build_context(self):
        await self.memory.add_message(
            session_id="s1",
            user_id="u1",
            role="user",
            content="مرحبا",
        )
        context = await self.builder.build_context("s1", "u1", "سؤال جديد")
        assert "recent_history" in context
        assert "user_context" in context

    def test_format_context_for_llm(self):
        context = {
            "recent_history": [
                {"role": "user", "content": "مرحبا"},
                {"role": "assistant", "content": "أهلاً"},
            ],
        }
        formatted = self.builder.format_context_for_llm(context)
        assert "مرحبا" in formatted


class TestAgentContextManager:
    """Test AgentContextManager functionality."""

    def setup_method(self):
        self.memory = ConversationMemory()
        self.manager = AgentContextManager(self.memory)

    @pytest.mark.asyncio
    async def test_enrich_query(self):
        context = await self.manager.enrich_query(
            session_id="s1",
            user_id="u1",
            query="ما هي مبيعات اليوم؟",
            agent="analytical",
        )
        assert "agent" in context
        assert context["agent"] == "analytical"
        assert "enrichments" in context

    @pytest.mark.asyncio
    async def test_record_interaction(self):
        await self.manager.record_interaction(
            session_id="s1",
            user_id="u1",
            query="سؤال",
            response="إجابة",
            agent="analytical",
        )
        history = await self.memory.get_history("s1", user_id="u1")
        assert len(history) == 2

    def test_is_follow_up(self):
        assert self.manager._is_follow_up("و أريد المزيد", []) is True
        assert self.manager._is_follow_up("مرحبا", []) is False

    def test_extract_topic(self):
        history = [{"role": "user", "content": "مبيعات اليوم"}]
        topic = self.manager._extract_topic(history)
        assert topic == "sales"

    def test_estimate_expertise(self):
        assert self.manager._estimate_expertise({"total_messages": 100}) == "expert"
        assert self.manager._estimate_expertise({"total_messages": 20}) == "intermediate"
        assert self.manager._estimate_expertise({"total_messages": 5}) == "beginner"
