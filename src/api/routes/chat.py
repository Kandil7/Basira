"""
Chat endpoint — supervisor entry point.

This is the main API endpoint that accepts user queries, runs them
through the LangGraph supervisor, and returns the agent's response.

Phase 2: Added session history support for multi-turn conversations.
"""

import time
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
import structlog

from src.agents.state import create_initial_state

logger = structlog.get_logger(__name__)

router = APIRouter()


class ChatRequest(BaseModel):
    """Chat request schema — consumed by /chat endpoint and n8n workflows."""

    query: str = Field(
        ...,
        description="User query text (Arabic or English)",
        min_length=1,
        max_length=5000,
        examples=["ما هي مبيعات فرع الرياض اليوم؟"],
    )
    channel: str = Field(
        default="web",
        description="Originating channel: web, whatsapp, api, n8n",
        examples=["web", "whatsapp"],
    )
    session_id: str | None = Field(
        default=None,
        description="Session ID for conversation history (auto-generated if not provided)",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional metadata: user_id, session_id, customer_phone, etc.",
        examples=[{"user_id": "U123", "session_id": "S456"}],
    )


class ChatResponse(BaseModel):
    """
    Chat response schema — returned by /chat endpoint.

    Phase 2 fields:
    - session_id: Session identifier for follow-up messages
    - message_count: Number of messages in this session
    """

    response: str = Field(..., description="Agent response text")
    intent: str = Field(..., description="Classified intent: analytics, cx, internal_ops, general")
    agent: str | None = Field(
        default=None,
        description="Agent that handled the request: analytical, cx, internal_ops, general",
    )
    session_id: str = Field(
        ...,
        description="Session ID for follow-up messages",
    )
    message_count: int = Field(
        default=1,
        description="Total messages in this session",
    )
    tools_used: list[str] = Field(
        default_factory=list,
        description="Tools invoked during processing",
    )
    sources: list[str] = Field(
        default_factory=list,
        description="Source references (doc:xxx, order:xxx, customer:xxx)",
    )
    processing_time_ms: float = Field(
        ...,
        description="Total processing time in milliseconds",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Response metadata (channel, model, etc.)",
    )


@router.post("/chat", response_model=ChatResponse)
async def chat(request: Request, body: ChatRequest) -> ChatResponse:
    """
    Chat with the AI agents platform.

    This is the supervisor entry point. The query is classified and routed
    to the appropriate agent (analytics, CX, internal ops, or general).

    **Session support**: Pass the returned `session_id` in subsequent requests
    to maintain conversation context.

    **n8n integration**: Pass `X-Internal-Key` header for authentication.

    **Supported channels**: web, whatsapp, api, n8n
    """
    start_time = time.time()

    compiled_graph = request.app.state.compiled_graph
    if compiled_graph is None:
        raise HTTPException(status_code=503, detail="Agent system not initialized")

    # Resolve session
    session_store = request.app.state.session_store
    import uuid
    session_id = body.session_id or str(uuid.uuid4())
    session = session_store.get_or_create(session_id)

    # Get conversation history
    history = session.get_history(limit=10)
    history_context = ""
    if history:
        history_lines = [f"{'العميل' if msg['role'] == 'user' else 'المساعد'}: {msg['content']}" for msg in history]
        history_context = "Previous conversation:\n" + "\n".join(history_lines) + "\n\n"

    # Build initial state with history
    metadata = {**body.metadata, "channel": body.channel, "session_id": session_id}
    initial_state = create_initial_state(body.query, metadata)

    try:
        # Run the supervisor graph
        result = await compiled_graph.ainvoke(initial_state)

        processing_time = (time.time() - start_time) * 1000

        # Store messages in session
        session_store.add_message(session_id, "user", body.query)
        session_store.add_message(session_id, "assistant", result.get("response", ""))

        logger.info(
            "chat.completed",
            query=body.query[:100],
            intent=result.get("intent", "unknown"),
            agent=result.get("agent"),
            session_id=session_id,
            processing_time_ms=processing_time,
        )

        return ChatResponse(
            response=result.get("response", "No response generated"),
            intent=result.get("intent", "general"),
            agent=result.get("agent"),
            session_id=session_id,
            message_count=session.message_count,
            tools_used=result.get("tools_used", []),
            sources=result.get("sources", []),
            processing_time_ms=round(processing_time, 2),
            metadata={
                "channel": body.channel,
                "model": request.app.state.settings.groq_model,
            },
        )

    except Exception as e:
        logger.error("chat.error", error=str(e), query=body.query[:100])
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "AGENT_ERROR",
                    "message": "Failed to process chat request",
                    "details": {"error": str(e)},
                }
            },
        )
