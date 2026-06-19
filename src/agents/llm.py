"""
Groq LLM client — shared wrapper for Groq API (groq.com).

Uses the OpenAI-compatible client with Groq's base URL.
All agent nodes call llm_chat() / llm_chat_json() instead of
instantiating ChatOpenAI (which has broken langchain-openai deps).

Phase 2: Added timeout support and circuit breaker integration.
"""

import asyncio

import openai
import structlog

from src.config.settings import Settings

logger = structlog.get_logger(__name__)

# Module-level client cache
_client: openai.AsyncOpenAI | None = None


def _get_client(settings: Settings) -> openai.AsyncOpenAI:
    """Get or create the cached async OpenAI client pointing at Groq."""
    global _client
    if _client is None:
        _client = openai.AsyncOpenAI(
            api_key=settings.groq_api_key,
            base_url=settings.groq_base_url,
        )
        logger.info("groq.client_initialized", base_url=settings.groq_base_url)
    return _client


async def llm_chat(
    settings: Settings,
    system_prompt: str,
    user_message: str,
    temperature: float = 0.3,
    timeout_seconds: float = 30.0,
) -> str:
    """
    Send a chat completion request to Groq and return the text response.

    Args:
        settings: Application settings (API key, model)
        system_prompt: System message content
        user_message: User message content
        temperature: Sampling temperature
        timeout_seconds: Maximum wait time before timeout

    Returns:
        Assistant response text, or timeout error message.
    """
    client = _get_client(settings)

    async def _call() -> str:
        response = await client.chat.completions.create(
            model=settings.groq_model,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        )
        content = response.choices[0].message.content or ""
        logger.info(
            "groq.chat",
            model=settings.groq_model,
            prompt_tokens=response.usage.prompt_tokens if response.usage else 0,
            completion_tokens=response.usage.completion_tokens if response.usage else 0,
        )
        return content

    try:
        return await asyncio.wait_for(_call(), timeout=timeout_seconds)
    except asyncio.TimeoutError:
        logger.warning(
            "groq.chat_timeout",
            model=settings.groq_model,
            timeout=timeout_seconds,
        )
        return "أعتذر، استغرق الطلب وقتاً أطول من المتوقع. يرجى المحاولة مرة أخرى."
    except Exception as e:
        logger.error("groq.chat_error", model=settings.groq_model, error=str(e))
        return f"حدث خطأ في معالجة طلبك. يرجى المحاولة لاحقاً."


async def llm_chat_json(
    settings: Settings,
    system_prompt: str,
    user_message: str,
    temperature: float = 0.0,
    timeout_seconds: float = 15.0,
) -> str:
    """
    Send a chat completion request expecting JSON output.

    Uses Groq's JSON mode.

    Args:
        settings: Application settings
        system_prompt: System message
        user_message: User message
        temperature: Sampling temperature (default 0 for classification)
        timeout_seconds: Maximum wait time (shorter for classification)

    Returns:
        Response text (JSON string), or fallback JSON on error.
    """
    client = _get_client(settings)

    async def _call() -> str:
        response = await client.chat.completions.create(
            model=settings.groq_model,
            temperature=temperature,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        )
        content = response.choices[0].message.content or ""
        logger.info(
            "groq.chat_json",
            model=settings.groq_model,
            tokens=response.usage.total_tokens if response.usage else 0,
        )
        return content

    try:
        return await asyncio.wait_for(_call(), timeout=timeout_seconds)
    except asyncio.TimeoutError:
        logger.warning(
            "groq.chat_json_timeout",
            model=settings.groq_model,
            timeout=timeout_seconds,
        )
        return '{"intent": "general"}'
    except Exception as e:
        logger.error("groq.chat_json_error", model=settings.groq_model, error=str(e))
        return '{"intent": "general"}'
