"""
Tests for the embeddings infrastructure module.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.infrastructure.embeddings.providers import (
    EmbeddingProvider,
    PlaceholderProvider,
)
from src.infrastructure.embeddings.cache import EmbeddingCache
from src.infrastructure.embeddings.preprocessing import (
    ArabicTextPreprocessor,
    arabic_preprocessor,
)
from src.infrastructure.embeddings.service import EmbeddingService


class TestPlaceholderProvider:
    """Test PlaceholderProvider functionality."""

    def setup_method(self):
        self.provider = PlaceholderProvider()

    def test_name(self):
        assert self.provider.name == "placeholder"

    def test_dimension(self):
        assert self.provider.dimension == 1536

    @pytest.mark.asyncio
    async def test_embed_returns_vector(self):
        embedding = await self.provider.embed("test text")
        assert isinstance(embedding, list)
        assert len(embedding) == 1536
        assert all(isinstance(v, float) for v in embedding)

    @pytest.mark.asyncio
    async def test_embed_deterministic(self):
        emb1 = await self.provider.embed("hello world")
        emb2 = await self.provider.embed("hello world")
        assert emb1 == emb2

    @pytest.mark.asyncio
    async def test_embed_different_texts(self):
        emb1 = await self.provider.embed("hello")
        emb2 = await self.provider.embed("world")
        assert emb1 != emb2

    @pytest.mark.asyncio
    async def test_embed_batch(self):
        embeddings = await self.provider.embed_batch(["a", "b", "c"])
        assert len(embeddings) == 3
        assert all(len(e) == 1536 for e in embeddings)

    @pytest.mark.asyncio
    async def test_embed_empty_batch(self):
        embeddings = await self.provider.embed_batch([])
        assert embeddings == []

    @pytest.mark.asyncio
    async def test_health_check(self):
        assert await self.provider.health_check() is True


class TestArabicTextPreprocessor:
    """Test Arabic text preprocessing."""

    def setup_method(self):
        self.preprocessor = ArabicTextPreprocessor()

    def test_normalize_removes_diacritics(self):
        # Text with diacritics (fatha, damma, kasra)
        text = "بِسْمِ ٱللَّٰهِ ٱلرَّحْمَٰنِ ٱلرَّحِيمِ"
        result = self.preprocessor.normalize(text)
        # Diacritics should be removed
        assert "\u064B" not in result  # fathatan
        assert "\u064C" not in result  # dammatan
        assert "\u064D" not in result  # kasratan

    def test_normalize_removes_tatweel(self):
        text = "محمدـــ"
        result = self.preprocessor.normalize(text)
        assert "\u0640" not in result

    def test_normalize_alef_variants(self):
        # All alef variants should normalize to standard alef
        text = "آب أ إ ٱ"
        result = self.preprocessor.normalize(text)
        assert "آ" not in result
        assert "أ" not in result
        assert "إ" not in result

    def test_normalize_whitespace(self):
        text = "  hello   world  "
        result = self.preprocessor.normalize(text)
        assert result == "hello world"

    def test_preprocess_removes_urls(self):
        text = "visit https://example.com for more info"
        result = self.preprocessor.preprocess_for_embedding(text)
        assert "https://" not in result

    def test_preprocess_removes_emails(self):
        text = "contact us at info@example.com"
        result = self.preprocessor.preprocess_for_embedding(text)
        assert "@" not in result or "info" not in result

    def test_expand_query_short(self):
        query = "كم مبيعات اليوم"
        result = self.preprocessor.expand_query(query)
        # Should expand "كم" to "كم عدد"
        assert "عدد" in result

    def test_expand_query_long_no_expand(self):
        query = "ما هي مبيعات فرع الرياض اليوم وأين الموقع"
        result = self.preprocessor.expand_query(query)
        # Long queries should not be expanded
        assert result == query

    def test_global_preprocessor(self):
        assert arabic_preprocessor is not None
        assert isinstance(arabic_preprocessor, ArabicTextPreprocessor)


class TestEmbeddingCache:
    """Test EmbeddingCache functionality."""

    def setup_method(self):
        self.cache = EmbeddingCache(redis_client=None)

    @pytest.mark.asyncio
    async def test_get_miss(self):
        result = await self.cache.get("test text", "model")
        assert result is None

    @pytest.mark.asyncio
    async def test_set_and_get(self):
        embedding = [0.1, 0.2, 0.3]
        await self.cache.set("test text", "model", embedding)
        result = await self.cache.get("test text", "model")
        assert result == embedding

    @pytest.mark.asyncio
    async def test_different_models_different_keys(self):
        embedding = [0.1, 0.2, 0.3]
        await self.cache.set("test text", "model_a", embedding)
        result_a = await self.cache.get("test text", "model_a")
        result_b = await self.cache.get("test text", "model_b")
        assert result_a == embedding
        assert result_b is None

    @pytest.mark.asyncio
    async def test_invalidate(self):
        embedding = [0.1, 0.2, 0.3]
        await self.cache.set("test text", "model", embedding)
        removed = await self.cache.invalidate("test text", "model")
        assert removed is True
        result = await self.cache.get("test text", "model")
        assert result is None

    @pytest.mark.asyncio
    async def test_clear(self):
        await self.cache.set("text1", "model", [0.1])
        await self.cache.set("text2", "model", [0.2])
        count = await self.cache.clear()
        assert count >= 2

    @pytest.mark.asyncio
    async def test_stats(self):
        await self.cache.get("miss", "model")
        stats = self.cache.get_stats()
        assert "hits" in stats
        assert "misses" in stats
        assert "hit_rate" in stats

    @pytest.mark.asyncio
    async def test_batch_get(self):
        await self.cache.set("text1", "model", [0.1])
        texts = ["text1", "text2", "text3"]
        misses, results = await self.cache.get_batch(texts, "model")
        assert len(results) == 3
        assert results[0] == [0.1]
        assert results[1] is None
        assert results[2] is None
        assert 1 in misses
        assert 2 in misses


class TestEmbeddingService:
    """Test EmbeddingService with PlaceholderProvider."""

    def setup_method(self):
        # Create a mock settings that has no API keys
        self.settings = MagicMock()
        self.settings.openai_api_key = ""
        self.settings.jina_api_key = ""
        self.settings.embedding_local_model = ""
        self.service = EmbeddingService(self.settings, redis_client=None)

    def test_provider_is_placeholder(self):
        assert self.service.provider_name == "placeholder"

    def test_dimension(self):
        assert self.service.dimension == 1536

    @pytest.mark.asyncio
    async def test_embed(self):
        embedding = await self.service.embed("test text")
        assert isinstance(embedding, list)
        assert len(embedding) == 1536

    @pytest.mark.asyncio
    async def test_embed_batch(self):
        embeddings = await self.service.embed_batch(["a", "b", "c"])
        assert len(embeddings) == 3

    @pytest.mark.asyncio
    async def test_embed_uses_cache(self):
        # First call
        emb1 = await self.service.embed("cached text")
        # Second call should hit cache
        emb2 = await self.service.embed("cached text")
        assert emb1 == emb2

    @pytest.mark.asyncio
    async def test_health_check(self):
        health = await self.service.health_check()
        assert health["status"] == "healthy"
        assert health["provider"] == "placeholder"

    def test_stats(self):
        stats = self.service.get_stats()
        assert "provider" in stats
        assert "total_embeds" in stats
        assert "cache_hit_rate" in stats

    @pytest.mark.asyncio
    async def test_embed_with_use_cache_false(self):
        emb1 = await self.service.embed("no cache text", use_cache=False)
        emb2 = await self.service.embed("no cache text", use_cache=False)
        # Both should work (deterministic placeholder)
        assert emb1 == emb2
