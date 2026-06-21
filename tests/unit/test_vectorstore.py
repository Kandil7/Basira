"""
Qdrant vector store tests — production vector store with advanced features.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from src.infrastructure.rag.vectorstore import (
    ProductionVectorStore,
    VectorStoreMetrics,
)


class TestVectorStoreMetrics:
    """Test metrics tracking."""

    def setup_method(self):
        self.metrics = VectorStoreMetrics()

    def test_record_search(self):
        self.metrics.record_search(10.5, 5)
        assert self.metrics.total_searches == 1
        assert self.metrics.search_latencies == [10.5]

    def test_record_upsert(self):
        self.metrics.record_upsert(25.0, 100)
        assert self.metrics.total_upserts == 1
        assert self.metrics.upsert_latencies == [25.0]

    def test_record_delete(self):
        self.metrics.record_delete()
        assert self.metrics.total_deletes == 1

    def test_record_error(self):
        self.metrics.record_error()
        assert self.metrics.total_errors == 1

    def test_latency_limit(self):
        for i in range(1500):
            self.metrics.record_search(float(i), 1)
        assert len(self.metrics.search_latencies) == 1000

    def test_get_stats(self):
        self.metrics.record_search(10.0, 5)
        self.metrics.record_search(20.0, 3)
        stats = self.metrics.get_stats()
        assert stats["total_searches"] == 2
        assert stats["avg_search_latency_ms"] == 15.0


class TestProductionVectorStore:
    """Test ProductionVectorStore with mocked Qdrant client."""

    def setup_method(self):
        self.settings = MagicMock()
        self.settings.qdrant_host = "localhost"
        self.settings.qdrant_port = 6333
        self.settings.qdrant_collection = "test_collection"

        with patch("src.infrastructure.rag.vectorstore.QdrantClient"):
            self.store = ProductionVectorStore(self.settings)

    def test_resolve_collection_default(self):
        result = self.store._resolve_collection(None)
        assert result == "test_collection"

    def test_resolve_collection_custom(self):
        result = self.store._resolve_collection("custom")
        assert result == "custom"

    def test_resolve_collection_with_namespace(self):
        store = ProductionVectorStore(self.settings, namespace="tenant1")
        result = store._resolve_collection("docs")
        assert result == "tenant1_docs"

    def test_resolve_collection_namespace_default(self):
        store = ProductionVectorStore(self.settings, namespace="tenant1")
        result = store._resolve_collection(None)
        assert result == "tenant1_test_collection"

    def test_build_filter_none(self):
        result = self.store._build_filter(None)
        assert result is None

    def test_build_filter_simple_match(self):
        result = self.store._build_filter({"status": "active"})
        assert result is not None
        assert len(result.must) == 1

    def test_build_filter_range(self):
        result = self.store._build_filter({"score": {"$gte": 0.5, "$lte": 1.0}})
        assert result is not None
        assert len(result.must) == 1

    def test_build_filter_match_any(self):
        result = self.store._build_filter({"category": {"$any": ["food", "drink"]}})
        assert result is not None
        assert len(result.must) == 1

    def test_build_filter_multiple_conditions(self):
        result = self.store._build_filter({
            "status": "active",
            "score": {"$gte": 0.5},
        })
        assert result is not None
        assert len(result.must) == 2

    def test_build_filter_and(self):
        result = self.store._build_filter({
            "$and": [{"status": "active"}, {"type": "doc"}],
        })
        assert result is not None

    def test_build_filter_or(self):
        result = self.store._build_filter({
            "$or": [{"status": "active"}, {"status": "pending"}],
        })
        assert result is not None
        assert result.should is not None

    def test_metrics_tracked(self):
        assert self.store.get_metrics()["total_searches"] == 0
        assert self.store.get_metrics()["total_upserts"] == 0
