"""
Voice API routes.

Provides endpoints for speech-to-text, text-to-speech, and full voice interaction.
"""

import io
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import structlog

from src.infrastructure.voice.asr import ASRLanguage

logger = structlog.get_logger(__name__)

router = APIRouter()


class VoiceChatRequest(BaseModel):
    """Request for voice chat (text-based, returns audio)."""
    query: str = Field(..., description="Text query to process")
    voice: str = Field(default="tara", description="TTS voice preset")
    speed: float = Field(default=1.0, ge=0.25, le=4.0, description="Speech speed")
    session_id: str | None = Field(None, description="Session ID for context")


class VoiceResponse(BaseModel):
    """Response from voice endpoints."""
    text: str
    audio_size_bytes: int
    audio_format: str
    processing_time_ms: float


@router.post("/voice/transcribe")
async def transcribe_audio(
    file: UploadFile = File(..., description="Audio file to transcribe"),
    language: str = Form(default="ar", description="Language code (ar, en, auto)"),
) -> dict[str, Any]:
    """
    Transcribe audio to text using Groq Whisper.

    Supports Arabic, English, and auto-detection.
    Accepts: WAV, MP3, OGG, FLAC, WebM, M4A
    Max size: 25MB
    """
    # Get voice service from app state
    # This will be wired in main.py
    try:
        from src.api.main import app
        voice_pipeline = getattr(app.state, "voice_pipeline", None)
        if not voice_pipeline:
            raise HTTPException(status_code=503, detail="Voice service not initialized")

        # Read audio data
        audio_data = await file.read()

        # Map language string to enum
        lang_map = {
            "ar": ASRLanguage.ARABIC,
            "en": ASRLanguage.ENGLISH,
            "auto": ASRLanguage.AUTO,
        }
        language_enum = lang_map.get(language, ASRLanguage.AUTO)

        # Transcribe
        result = await voice_pipeline.transcribe_only(
            audio_data=audio_data,
            language=language_enum,
            filename=file.filename or "audio.wav",
        )

        return {
            "text": result.text,
            "language": result.language,
            "confidence": result.confidence,
            "duration_seconds": result.duration_seconds,
            "processing_time_ms": round(result.processing_time_ms, 2),
            "model": result.model,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("voice.transcribe_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/voice/synthesize")
async def synthesize_speech(
    body: VoiceChatRequest,
) -> StreamingResponse:
    """
    Convert text to speech using Groq Orpheus.

    Returns audio stream in MP3 format.
    """
    try:
        from src.api.main import app
        voice_pipeline = getattr(app.state, "voice_pipeline", None)
        if not voice_pipeline:
            raise HTTPException(status_code=503, detail="Voice service not initialized")

        # Synthesize speech
        result = await voice_pipeline.synthesize_only(
            text=body.query,
            voice=body.voice,
            speed=body.speed,
        )

        # Return audio stream
        return StreamingResponse(
            io.BytesIO(result.audio_data),
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": f"attachment; filename=speech.{result.format}",
                "X-TTS-Processing-Time-Ms": str(round(result.processing_time_ms, 2)),
                "X-TTS-Voice": result.voice,
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("voice.synthesize_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/voice/chat")
async def voice_chat(
    file: UploadFile = File(..., description="Audio file to process"),
    voice: str = Form(default="tara", description="TTS voice preset"),
    speed: float = Form(default=1.0, description="Speech speed"),
    session_id: str | None = Form(default=None, description="Session ID"),
) -> StreamingResponse:
    """
    Full voice interaction: Audio → Text → Agent → Audio.

    Accepts audio input, processes through the agent pipeline,
    and returns audio response.
    """
    try:
        from src.api.main import app
        voice_pipeline = getattr(app.state, "voice_pipeline", None)
        if not voice_pipeline:
            raise HTTPException(status_code=503, detail="Voice service not initialized")

        # Read audio data
        audio_data = await file.read()

        # Build voice request
        from src.infrastructure.voice.pipeline import VoiceRequest
        request = VoiceRequest(
            audio_data=audio_data,
            filename=file.filename or "audio.wav",
            language=ASRLanguage.ARABIC,
            voice=voice,
            speed=speed,
            session_id=session_id,
        )

        # Process through full pipeline
        result = await voice_pipeline.process(request)

        # Return audio response
        return StreamingResponse(
            io.BytesIO(result.audio_data),
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": f"attachment; filename=response.{result.audio_format}",
                "X-ASR-Text": result.transcribed_text,
                "X-ASR-Language": result.asr_language,
                "X-Agent-Intent": result.agent_intent,
                "X-Agent-Name": result.agent_agent,
                "X-Total-Time-Ms": str(round(result.total_processing_time_ms, 2)),
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("voice.chat_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/voice/chat/text")
async def voice_chat_text(
    body: VoiceChatRequest,
) -> dict[str, Any]:
    """
    Text-to-voice chat: Text → Agent → Text + Audio URL.

    Process text through agent and return both text response
    and audio synthesis.
    """
    try:
        from src.api.main import app
        voice_pipeline = getattr(app.state, "voice_pipeline", None)
        if not voice_pipeline:
            raise HTTPException(status_code=503, detail="Voice service not initialized")

        # Process through agent
        agent_result = await voice_pipeline._agent_fn(
            body.query,
            body.session_id,
        )

        agent_response = agent_result.get("response", "")

        # Synthesize speech
        tts_result = await voice_pipeline.synthesize_only(
            text=agent_response,
            voice=body.voice,
            speed=body.speed,
        )

        return {
            "text": agent_response,
            "intent": agent_result.get("intent", "unknown"),
            "agent": agent_result.get("agent", "unknown"),
            "audio_size_bytes": tts_result.size_bytes,
            "audio_format": tts_result.format,
            "processing_time_ms": round(
                tts_result.processing_time_ms, 2
            ),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("voice.chat_text_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/voice/health")
async def voice_health() -> dict[str, Any]:
    """Check voice service health."""
    try:
        from src.api.main import app
        voice_pipeline = getattr(app.state, "voice_pipeline", None)
        if not voice_pipeline:
            return {"status": "unavailable", "reason": "Voice service not initialized"}

        asr_health = await voice_pipeline._asr.health_check()
        tts_health = await voice_pipeline._tts.health_check()

        return {
            "status": "healthy" if asr_health["status"] == "healthy" and tts_health["status"] == "healthy" else "degraded",
            "asr": asr_health,
            "tts": tts_health,
            "stats": voice_pipeline.get_stats(),
        }

    except Exception as e:
        return {"status": "error", "error": str(e)}
