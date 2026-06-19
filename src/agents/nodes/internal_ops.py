"""
Internal Ops Agent node.

Handles document summarization, KPI extraction, and task generation.
Uses document service + Groq LLM for processing uploaded reports.

Prompt loaded from: prompts/internal_ops_prompt.txt

Phase 4: Enhanced with dedicated ops tools (summarize, extract_kpis, generate_tasks).
"""

import re
from typing import Any

import structlog

from src.agents.llm import llm_chat
from src.agents.prompts import INTERNAL_OPS_PROMPT
from src.agents.state import AgentState
from src.config.settings import Settings
from src.domain.services.document_service import DocumentService

logger = structlog.get_logger(__name__)


async def internal_ops_node(
    state: AgentState,
    settings: Settings,
    document_service: DocumentService,
) -> dict[str, Any]:
    """
    Internal ops agent node — handles document processing and KPI extraction.

    Uses DocumentService for RAG retrieval and Groq LLM for analysis.
    Detects intent keywords to apply specialized tools:
    - summarize: Report summarization
    - kpi / مؤشرات: KPI extraction
    - مهمة / task: Task generation

    Args:
        state: Current agent state
        settings: Application settings
        document_service: Domain service for document processing

    Returns:
        State update with ops response.
    """
    query = state.get("user_query", "")
    context_parts: list[str] = []
    sources: list[str] = []
    tools_used: list[str] = []

    # ── Step 1: Search for relevant documents in Qdrant ──────────────
    try:
        docs = await document_service.search_documents(query, limit=5)
        if docs:
            doc_context = "\n\n".join(d.content for d in docs)
            context_parts.append(f"Relevant Documents:\n{doc_context}")
            tools_used.append("document_retrieval")
            for d in docs:
                if d.document_id:
                    sources.append(f"doc:{d.document_id}")
    except Exception as e:
        logger.warning("internal_ops.rag_error", error=str(e))

    # ── Step 2: Detect specialized ops intent ─────────────────────────
    is_summarize = any(w in query for w in ["لخص", "summary", "summarize", "تلخيص"])
    is_kpi = any(w in query for w in ["kpi", "مؤشر", "مؤشرات", "metric", "أداء"])
    is_tasks = any(w in query for w in ["مهمة", "مهام", "task", "tasks", "قائمة"])

    # Build context-aware prompt
    context = "\n\n".join(context_parts) if context_parts else "لا توجد مستندات محددة متاحة."

    if is_summarize:
        specialized_prompt = (
            "أنت خبير في تلخيص التقارير. "
            "قدم ملخصاً منظماً يشمل ملخصاً تنفيذياً، وأهم النتائج، والاتجاهات."
        )
        tools_used.append("summarize_report")
    elif is_kpi:
        specialized_prompt = (
            "أنت خبير في استخراج المؤشرات الرئيسية. "
            "استخرج جميع مؤشرات الأداء الرئيسية مع قيمها ووحداتها واتجاهاتها. "
            "arrange them as a structured list."
        )
        tools_used.append("extract_kpis")
    elif is_tasks:
        specialized_prompt = (
            "أنت مدير تشغيل ينشئ قوائم مهام من التقارير. "
            "أنشئ قائمة مهام مرتبة حسب الأولوية مع الأوصاف والمستوى والمسؤول المقترح والمواعيد النهائية. "
            "اجعل المهام عملية ومحددة."
        )
        tools_used.append("generate_tasks")
    else:
        specialized_prompt = INTERNAL_OPS_PROMPT

    # ── Step 3: Generate response via Groq ───────────────────────────
    user_msg = f"Context:\n{context}\n\nRequest: {query}"

    try:
        response_text = await llm_chat(
            settings=settings,
            system_prompt=specialized_prompt,
            user_message=user_msg,
            temperature=0.3,
        )
    except Exception as e:
        logger.error("internal_ops.llm_error", error=str(e))
        response_text = "أعتذر، حدث خطأ أثناء معالجة طلبك. يرجى المحاولة مرة أخرى."

    logger.info(
        "internal_ops.response_generated",
        query=query[:100],
        tools_used=tools_used,
        response_length=len(response_text),
    )

    return {
        "response": response_text,
        "agent": "internal_ops",
        "context": {"documents": context_parts},
        "tools_used": tools_used,
        "sources": sources,
    }


def create_internal_ops_node(
    settings: Settings,
    document_service: DocumentService,
):
    """Factory to create internal ops node with dependencies."""

    async def node(state: AgentState) -> dict[str, Any]:
        return await internal_ops_node(state, settings, document_service)

    return node
