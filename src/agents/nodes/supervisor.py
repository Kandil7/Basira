"""
Supervisor node — classifies user intent and routes to the appropriate agent.

Uses Groq LLM to determine whether the query is about analytics,
customer service, internal operations, or general conversation.

Prompt loaded from: prompts/supervisor_prompt.txt
"""

import json
from typing import Any

import structlog

from src.agents.llm import llm_chat_json
from src.agents.prompts import SUPERVISOR_PROMPT
from src.agents.state import AgentState
from src.config.settings import Settings

logger = structlog.get_logger(__name__)


async def supervisor_node(state: AgentState, settings: Settings) -> dict[str, Any]:
    """
    Supervisor node that classifies intent and routes to agents.

    Uses Groq LLM to determine the user's intent, then updates the
    state with the classification for downstream routing.

    Args:
        state: Current agent state
        settings: Application settings

    Returns:
        State update with intent classification.
    """
    query = state.get("user_query", "")

    # Classify intent via Groq
    response_text = await llm_chat_json(
        settings=settings,
        system_prompt=SUPERVISOR_PROMPT,
        user_message=f"Classify this query: {query}",
        temperature=0.0,
    )

    # Parse intent from JSON response
    try:
        parsed = json.loads(response_text)
        intent_text = parsed.get("intent", "general").strip().lower()
    except (json.JSONDecodeError, AttributeError):
        intent_text = response_text.strip().strip('"').lower()

    valid_intents = {"analytics", "cx", "internal_ops", "general"}
    intent = intent_text if intent_text in valid_intents else "general"

    logger.info(
        "supervisor.classified",
        query=query[:100],
        intent=intent,
    )

    return {
        "intent": intent,
        "task": f"Handle {intent} request",
    }


def create_supervisor_node(settings: Settings):
    """Factory to create supervisor node with settings closure."""

    async def node(state: AgentState) -> dict[str, Any]:
        return await supervisor_node(state, settings)

    return node
