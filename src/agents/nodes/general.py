"""
General fallback node.

Handles greetings, off-topic queries, and unclear requests via Groq LLM.

Prompt loaded from: prompts/general_prompt.txt
"""

from typing import Any

import structlog

from src.agents.llm import llm_chat
from src.agents.prompts import GENERAL_PROMPT
from src.agents.state import AgentState
from src.config.settings import Settings

logger = structlog.get_logger(__name__)


async def general_node(state: AgentState, settings: Settings) -> dict[str, Any]:
    """
    General fallback node for greetings and unclear queries.

    Args:
        state: Current agent state
        settings: Application settings

    Returns:
        State update with general response.
    """
    query = state.get("user_query", "")

    try:
        response_text = await llm_chat(
            settings=settings,
            system_prompt=GENERAL_PROMPT,
            user_message=query,
            temperature=0.5,
        )
    except Exception as e:
        logger.error("general.llm_error", error=str(e))
        response_text = "مرحباً! كيف يمكنني مساعدتك؟"

    logger.info("general.response_generated", query=query[:100])

    return {
        "response": response_text,
        "agent": "general",
        "tools_used": [],
    }


def create_general_node(settings: Settings):
    """Factory to create general node with settings closure."""

    async def node(state: AgentState) -> dict[str, Any]:
        return await general_node(state, settings)

    return node
