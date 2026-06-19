"""
Agent integration tests.

Tests the LangGraph supervisor, intent classification, and agent nodes
with mocked dependencies (no real LLM or Odoo calls).
"""

import pytest
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.state import AgentState, create_initial_state
from src.agents.nodes.supervisor import supervisor_node
from src.agents.nodes.analytical import analytical_node
from src.agents.nodes.cx import cx_node
from src.agents.nodes.internal_ops import internal_ops_node
from src.agents.nodes.general import general_node
from src.agents.graph import _route_by_intent, build_supervisor_graph, compile_graph
from src.domain.interfaces.odoo_client import OdooClientInterface
from src.domain.services.analytics_service import AnalyticsService
from src.domain.services.customer_service import CustomerService
from src.domain.services.document_service import DocumentService
from src.infrastructure.rag.retriever import Retriever


# ── Mock Odoo Client ────────────────────────────────────────────────

class MockOdooClient(OdooClientInterface):
    """Mock Odoo client for agent tests."""

    def __init__(self, orders: list[dict] | None = None):
        self._orders = orders or []
        self.search_read_mock = AsyncMock(return_value=self._orders)

    async def search_read(self, model, domain, fields, limit=100, offset=0, order=None):
        return await self.search_read_mock(model, domain, fields, limit, offset, order)

    async def read(self, model, ids, fields=None):
        return []

    async def fields_get(self, model, attributes=None):
        return {}

    async def execute_kw(self, model, method, args=None, kwargs=None):
        return None

    async def health_check(self):
        return True


# ── Mock Vector Store ───────────────────────────────────────────────

class MockVectorStore:
    """Mock vector store for agent tests."""

    def __init__(self, results: list[dict] | None = None):
        self._results = results or []
        self.search_mock = AsyncMock(return_value=self._results)
        self.upsert_mock = AsyncMock(return_value=True)

    async def search(self, collection_name, query_vector, limit=10, filter_dict=None):
        return await self.search_mock(collection_name, query_vector, limit, filter_dict)

    async def upsert(self, collection_name, points):
        return await self.upsert_mock(collection_name, points)

    async def create_collection(self, collection_name, vector_size=1536, distance="Cosine"):
        return True

    async def delete(self, collection_name, point_ids):
        return True

    async def get_collection_info(self, collection_name):
        return {}

    async def health_check(self):
        return True


# ── Fixtures ────────────────────────────────────────────────────────

@pytest.fixture
def mock_odoo_with_orders():
    """Odoo mock that returns sample orders."""
    return MockOdooClient(orders=[
        {"id": 1, "amount_total": 5000, "warehouse_id": 1, "date_order": "2025-01-15"},
        {"id": 2, "amount_total": 3000, "warehouse_id": 1, "date_order": "2025-01-15"},
    ])


@pytest.fixture
def mock_odoo_empty():
    """Odoo mock that returns no data."""
    return MockOdooClient(orders=[])


@pytest.fixture
def mock_vector_with_docs():
    """Vector store with sample documents."""
    return MockVectorStore(results=[
        {
            "id": "chunk1",
            "score": 0.95,
            "payload": {
                "content": "سياسة الإرجاع: يمكن إرجاع المنتجات خلال 30 يوماً",
                "document_id": "doc_policy1",
                "chunk_index": 0,
            },
        }
    ])


@pytest.fixture
def mock_vector_empty():
    """Vector store with no results."""
    return MockVectorStore(results=[])


@pytest.fixture
def settings():
    """Mock settings."""
    from src.config.settings import Settings
    return Settings(
        groq_api_key="test-key",
        groq_model="llama-3.3-70b-versatile",
        groq_base_url="https://api.groq.com/openai/v1",
    )


# ── Test: State Creation ────────────────────────────────────────────

class TestAgentState:
    """Test AgentState creation and properties."""

    def test_create_initial_state(self):
        """Initial state has correct defaults."""
        state = create_initial_state("Hello")
        assert state.user_query == "Hello"
        assert state.intent == "general"
        assert state.agent is None
        assert state.response == ""
        assert state.sources == []
        assert state.tools_used == []
        assert state.error is None

    def test_create_with_metadata(self):
        """Metadata is preserved."""
        state = create_initial_state("Test", {"channel": "whatsapp"})
        assert state["metadata"]["channel"] == "whatsapp"

    def test_state_properties(self):
        """Typed accessors work correctly."""
        state = AgentState(
            user_query="test",
            intent="analytics",
            agent="analytical",
            response="result",
            sources=["doc:1"],
            tools_used=["tool1"],
        )
        assert state.user_query == "test"
        assert state.intent == "analytics"
        assert state.agent == "analytical"
        assert state.response == "result"
        assert state.sources == ["doc:1"]
        assert state.tools_used == ["tool1"]


# ── Test: Intent Routing ────────────────────────────────────────────

class TestIntentRouting:
    """Test supervisor routing logic."""

    def test_route_analytics(self):
        state = AgentState(intent="analytics")
        assert _route_by_intent(state) == "analytical_agent"

    def test_route_cx(self):
        state = AgentState(intent="cx")
        assert _route_by_intent(state) == "cx_agent"

    def test_route_internal_ops(self):
        state = AgentState(intent="internal_ops")
        assert _route_by_intent(state) == "internal_ops_agent"

    def test_route_general_fallback(self):
        state = AgentState(intent="unknown")
        assert _route_by_intent(state) == "general_agent"

    def test_route_empty_defaults_to_general(self):
        state = AgentState()
        assert _route_by_intent(state) == "general_agent"


# ── Test: Supervisor Node (mocked LLM) ──────────────────────────────

class TestSupervisorNode:
    """Test supervisor classification with mocked LLM."""

    @pytest.mark.asyncio
    async def test_classifies_analytics(self, settings):
        """Supervisor classifies sales query as analytics."""
        state = create_initial_state("ما هي مبيعات اليوم؟")

        with patch("src.agents.nodes.supervisor.llm_chat_json", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = '{"intent": "analytics"}'
            result = await supervisor_node(state, settings)

        assert result["intent"] == "analytics"

    @pytest.mark.asyncio
    async def test_classifies_cx(self, settings):
        """Supervisor classifies order query as cx."""
        state = create_initial_state("أين طلبي رقم 123؟")

        with patch("src.agents.nodes.supervisor.llm_chat_json", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = '{"intent": "cx"}'
            result = await supervisor_node(state, settings)

        assert result["intent"] == "cx"

    @pytest.mark.asyncio
    async def test_classifies_internal_ops(self, settings):
        """Supervisor classifies report query as internal_ops."""
        state = create_initial_state("لخص تقرير المبيعات الشهري")

        with patch("src.agents.nodes.supervisor.llm_chat_json", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = '{"intent": "internal_ops"}'
            result = await supervisor_node(state, settings)

        assert result["intent"] == "internal_ops"

    @pytest.mark.asyncio
    async def test_invalid_intent_falls_back_to_general(self, settings):
        """Invalid intent from LLM falls back to general."""
        state = create_initial_state("مرحبا")

        with patch("src.agents.nodes.supervisor.llm_chat_json", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = '{"intent": "invalid_intent"}'
            result = await supervisor_node(state, settings)

        assert result["intent"] == "general"

    @pytest.mark.asyncio
    async def test_json_parse_error_falls_back(self, settings):
        """Malformed JSON from LLM falls back gracefully."""
        state = create_initial_state("test")

        with patch("src.agents.nodes.supervisor.llm_chat_json", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = "not valid json"
            result = await supervisor_node(state, settings)

        assert result["intent"] == "general"


# ── Test: Analytical Agent (mocked LLM + Odoo) ─────────────────────

class TestAnalyticalAgent:
    """Test analytical agent with mocked dependencies."""

    @pytest.mark.asyncio
    async def test_analytical_with_data(self, settings, mock_odoo_with_orders):
        """Analytical agent returns response with order data."""
        service = AnalyticsService(mock_odoo_with_orders)
        state = create_initial_state("ما هي مبيعات اليوم؟")

        with patch("src.agents.nodes.analytical.llm_chat", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = "مبيعات اليوم 8,000 ريال من 2 طلبات"
            result = await analytical_node(state, settings, service)

        assert result["agent"] == "analytical"
        assert "8,000" in result["response"]
        assert "analytics_service" in result["tools_used"]

    @pytest.mark.asyncio
    async def test_analytical_no_data(self, settings, mock_odoo_empty):
        """Analytical agent handles empty data gracefully."""
        service = AnalyticsService(mock_odoo_empty)
        state = create_initial_state("sales report")

        with patch("src.agents.nodes.analytical.llm_chat", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = "No sales data available for today."
            result = await analytical_node(state, settings, service)

        assert result["agent"] == "analytical"
        assert result["response"] == "No sales data available for today."


# ── Test: CX Agent (mocked LLM + RAG) ──────────────────────────────

class TestCXAgent:
    """Test CX agent with mocked dependencies."""

    @pytest.mark.asyncio
    async def test_cx_with_rag_context(self, settings, mock_vector_with_docs):
        """CX agent uses RAG context for policy questions."""
        mock_odoo = MockOdooClient()
        customer_service = CustomerService(mock_odoo)
        retriever = Retriever(mock_vector_with_docs, settings)

        state = create_initial_state("ما هي سياسة الإرجاع؟")

        with patch("src.agents.nodes.cx.llm_chat", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = "يمكنك إرجاع المنتجات خلال 30 يوماً من تاريخ الاستلام."
            result = await cx_node(state, settings, customer_service, retriever)

        assert result["agent"] == "cx"
        assert "30 يوماً" in result["response"]
        assert "rag_retrieval" in result["tools_used"]

    @pytest.mark.asyncio
    async def test_cx_order_lookup(self, settings, mock_vector_empty):
        """CX agent looks up order by ID."""
        mock_odoo = MockOdooClient(orders=[
            {
                "id": 123,
                "name": "SO00123",
                "partner_id": 1,
                "date_order": date.today(),
                "state": "sale",
                "amount_total": 500.0,
                "currency_id": 1,
                "warehouse_id": 1,
            }
        ])
        customer_service = CustomerService(mock_odoo)
        retriever = Retriever(mock_vector_empty, settings)

        state = create_initial_state("أين طلب #123؟")

        with patch("src.agents.nodes.cx.llm_chat", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = "طلبك SO00123 قيد التوصيل."
            result = await cx_node(state, settings, customer_service, retriever)

        assert result["agent"] == "cx"
        assert "order_lookup" in result["tools_used"]


# ── Test: Internal Ops Agent (mocked LLM + Qdrant) ─────────────────

class TestInternalOpsAgent:
    """Test internal ops agent with mocked dependencies."""

    @pytest.mark.asyncio
    async def test_ops_summarize(self, settings, mock_vector_with_docs):
        """Ops agent summarizes documents."""
        mock_odoo = MockOdooClient()
        doc_service = DocumentService(mock_vector_with_docs)

        state = create_initial_state("لخص التقارير المتوفرة")

        with patch("src.agents.nodes.internal_ops.llm_chat", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = "ملخص: التقرير يظهر نموًا في المبيعات بنسبة 15%"
            result = await internal_ops_node(state, settings, doc_service)

        assert result["agent"] == "internal_ops"
        assert "15%" in result["response"]
        assert "summarize_report" in result["tools_used"]

    @pytest.mark.asyncio
    async def test_ops_extract_kpis(self, settings, mock_vector_with_docs):
        """Ops agent extracts KPIs."""
        mock_odoo = MockOdooClient()
        doc_service = DocumentService(mock_vector_with_docs)

        state = create_initial_state("استخرج المؤشرات من التقرير")

        with patch("src.agents.nodes.internal_ops.llm_chat", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = "KPIs: إجمالي المبيعات 1.5M ريال، نمو 15%"
            result = await internal_ops_node(state, settings, doc_service)

        assert result["agent"] == "internal_ops"
        assert "extract_kpis" in result["tools_used"]

    @pytest.mark.asyncio
    async def test_ops_generate_tasks(self, settings, mock_vector_with_docs):
        """Ops agent generates task list."""
        mock_odoo = MockOdooClient()
        doc_service = DocumentService(mock_vector_with_docs)

        state = create_initial_state("أنشئ قائمة مهام من التقرير")

        with patch("src.agents.nodes.internal_ops.llm_chat", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = "1. مراجعة المخزون (عالي)\n2. تحديث الأسعار (متوسط)"
            result = await internal_ops_node(state, settings, doc_service)

        assert result["agent"] == "internal_ops"
        assert "generate_tasks" in result["tools_used"]


# ── Test: Graph Construction ────────────────────────────────────────

class TestGraphConstruction:
    """Test graph builder and compilation."""

    def test_graph_builds_and_compiles(self, settings):
        """Graph can be built and compiled without errors."""
        mock_odoo = MockOdooClient()
        mock_vs = MockVectorStore()

        analytics = AnalyticsService(mock_odoo)
        customer = CustomerService(mock_odoo)
        document = DocumentService(mock_vs)
        retriever = MagicMock()

        graph = build_supervisor_graph(
            settings=settings,
            analytics_service=analytics,
            customer_service=customer,
            document_service=document,
            retriever=retriever,
        )
        compiled = compile_graph(graph)

        assert compiled is not None
