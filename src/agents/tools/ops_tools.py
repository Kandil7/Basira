"""
Ops tools — LangChain tool definitions for internal operations.

Tools for report summarization, KPI extraction, and task generation.
Used by the Internal Ops Agent node.
"""

from typing import Any

from langchain_core.tools import tool
import structlog

logger = structlog.get_logger(__name__)

_document_service: Any = None
_llm_settings: Any = None


def set_ops_services(document_service: Any, settings: Any) -> None:
    """Set services for ops tool use."""
    global _document_service, _llm_settings
    _document_service = document_service
    _llm_settings = settings


@tool
async def summarize_report_tool(content: str, language: str = "ar") -> str:
    """
    Summarize report content using LLM.

    Args:
        content: Raw report text content to summarize
        language: Output language (ar for Arabic, en for English)

    Returns:
        Structured summary with key points.
    """
    if _llm_settings is None:
        return "LLM settings not initialized"

    try:
        from src.agents.llm import llm_chat

        prompt = f"""Summarize the following report in {language}.
Provide:
1. A 2-3 sentence executive summary
2. Key findings (bullet points)
3. Notable trends or anomalies

Report content:
{content[:4000]}"""

        summary = await llm_chat(
            settings=_llm_settings,
            system_prompt="You are an expert report analyst for a retail/food company.",
            user_message=prompt,
            temperature=0.3,
        )
        return summary
    except Exception as e:
        logger.error("tool.summarize_report_failed", error=str(e))
        return f"Error summarizing report: {str(e)}"


@tool
async def extract_kpis_tool(content: str) -> str:
    """
    Extract key performance indicators (KPIs) from report content.

    Args:
        content: Report text containing numerical data

    Returns:
        Structured list of extracted KPIs with values and units.
    """
    if _llm_settings is None:
        return "LLM settings not initialized"

    try:
        from src.agents.llm import llm_chat

        prompt = f"""Extract all KPIs (Key Performance Indicators) from this report.
For each KPI, provide:
- Name (in Arabic if the report is in Arabic)
- Value (numeric)
- Unit (SAR, %, count, etc.)
- Trend (up/down/stable) if determinable

Format as a structured list.

Report content:
{content[:4000]}"""

        kpis = await llm_chat(
            settings=_llm_settings,
            system_prompt="You are a KPI extraction expert for retail/food analytics.",
            user_message=prompt,
            temperature=0.2,
        )
        return kpis
    except Exception as e:
        logger.error("tool.extract_kpis_failed", error=str(e))
        return f"Error extracting KPIs: {str(e)}"


@tool
async def generate_tasks_tool(content: str, priority_filter: str = "all") -> str:
    """
    Generate actionable task list from report content.

    Args:
        content: Report text to generate tasks from
        priority_filter: Filter tasks by priority (all, high, medium, low)

    Returns:
        Numbered task list with priorities and assignments.
    """
    if _llm_settings is None:
        return "LLM settings not initialized"

    try:
        from src.agents.llm import llm_chat

        prompt = f"""Based on this report, generate a prioritized task list.
For each task provide:
- Task description (actionable, specific)
- Priority (high/medium/low)
- Suggested owner/team
- Deadline (if inferable)

{"Filter: only " + priority_filter + " priority tasks." if priority_filter != "all" else "Include all priority levels."}

Report content:
{content[:4000]}"""

        tasks = await llm_chat(
            settings=_llm_settings,
            system_prompt="You are an operations manager generating actionable tasks from reports.",
            user_message=prompt,
            temperature=0.3,
        )
        return tasks
    except Exception as e:
        logger.error("tool.generate_tasks_failed", error=str(e))
        return f"Error generating tasks: {str(e)}"


@tool
async def search_reports_tool(query: str, limit: int = 5) -> str:
    """
    Search stored reports in the vector database.

    Args:
        query: Search query for relevant reports
        limit: Maximum number of results

    Returns:
        Relevant report excerpts.
    """
    if _document_service is None:
        return "Document service not initialized"

    try:
        docs = await _document_service.search_documents(query, limit=limit)
        if not docs:
            return "No relevant reports found."

        parts: list[str] = []
        for i, doc in enumerate(docs, 1):
            parts.append(f"[Report {i}] (doc:{doc.document_id})\n{doc.content[:500]}")

        return "\n\n".join(parts)
    except Exception as e:
        logger.error("tool.search_reports_failed", error=str(e))
        return f"Error searching reports: {str(e)}"
