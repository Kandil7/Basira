"""
Voice pipeline — end-to-end voice interaction.

Combines ASR (speech-to-text), agent processing, and TTS (text-to-speech)
for a complete voice interaction loop.
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable

import structlog

from src.infrastructure.voice.asr import SpeechRecognizer, ASRResult, ASRLanguage
from src.infrastructure.voice.tts import SpeechSynthesizer, TTSResult, TTSFormat

logger = structlog.get_logger(__name__)


@dataclass
class VoiceRequest:
    """Input for voice pipeline."""
    audio_data: bytes
    filename: str = "audio.wav"
    language: ASRLanguage = ASRLanguage.ARABIC
    voice: str = "tara"
    speed: float = 1.0
    session_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class VoiceResponse:
    """Output from voice pipeline."""
    # ASR results
    transcribed_text: str
    asr_language: str
    asr_confidence: float
    asr_duration_seconds: float
    asr_processing_time_ms: float

    # Agent results
    agent_response: str
    agent_intent: str
    agent_agent: str

    # TTS results
    audio_data: bytes
    audio_format: str
    audio_duration_seconds: float
    tts_processing_time_ms: float

    # Total
    total_processing_time_ms: float

    @property
    def audio_size_bytes(self) -> int:
        return len(self.audio_data)


class VoicePipeline:
    """
    End-to-end voice interaction pipeline.

    Flow:
    1. Audio → ASR (Whisper) → Text
    2. Text → Agent → Response Text
    3. Response Text → TTS (Orpheus) → Audio

    Supports:
    - Arabic voice input/output
    - Multi-language ASR
    - Streaming responses
    - Session continuity
    """

    def __init__(
        self,
        asr: SpeechRecognizer,
        tts: SpeechSynthesizer,
        agent_fn: Callable[[str, str | None], Awaitable[dict[str, Any]]],
    ) -> None:
        """
        Initialize voice pipeline.

        Args:
            asr: Speech recognizer (Whisper)
            tts: Speech synthesizer (Orpheus)
            agent_fn: Async function that processes text and returns agent response
                      Signature: async def agent_fn(query: str, session_id: str | None) -> dict
                      Must return: {"response": str, "intent": str, "agent": str}
        """
        self._asr = asr
        self._tts = tts
        self._agent_fn = agent_fn
        self._stats = {
            "total_requests": 0,
            "successful": 0,
            "failed": 0,
            "avg_total_time_ms": 0,
        }

        logger.info("voice.pipeline_initialized")

    async def process(self, request: VoiceRequest) -> VoiceResponse:
        """
        Process a complete voice interaction.

        Args:
            request: VoiceRequest with audio data and options

        Returns:
            VoiceResponse with full pipeline results.
        """
        total_start = time.monotonic()
        self._stats["total_requests"] += 1

        try:
            # Step 1: ASR - Speech to Text
            asr_start = time.monotonic()
            asr_result = await self._asr.transcribe(
                audio_data=request.audio_data,
                language=request.language,
                filename=request.filename,
            )
            asr_time = (time.monotonic() - asr_start) * 1000

            logger.info(
                "voice.asr_complete",
                text_length=len(asr_result.text),
                language=asr_result.language,
                processing_time_ms=round(asr_time, 2),
            )

            # Step 2: Agent Processing
            agent_start = time.monotonic()
            agent_result = await self._agent_fn(
                asr_result.text,
                request.session_id,
            )
            agent_time = (time.monotonic() - agent_start) * 1000

            agent_response = agent_result.get("response", "")
            agent_intent = agent_result.get("intent", "unknown")
            agent_agent = agent_result.get("agent", "unknown")

            logger.info(
                "voice.agent_complete",
                intent=agent_intent,
                agent=agent_agent,
                response_length=len(agent_response),
                processing_time_ms=round(agent_time, 2),
            )

            # Step 3: TTS - Text to Speech
            tts_start = time.monotonic()
            tts_result = await self._tts.synthesize(
                text=agent_response,
                voice=request.voice,
                speed=request.speed,
            )
            tts_time = (time.monotonic() - tts_start) * 1000

            logger.info(
                "voice.tts_complete",
                audio_size=tts_result.size_bytes,
                processing_time_ms=round(tts_time, 2),
            )

            total_time = (time.monotonic() - total_start) * 1000

            # Update stats
            self._stats["successful"] += 1
            self._update_avg_time(total_time)

            return VoiceResponse(
                # ASR
                transcribed_text=asr_result.text,
                asr_language=asr_result.language,
                asr_confidence=asr_result.confidence,
                asr_duration_seconds=asr_result.duration_seconds,
                asr_processing_time_ms=asr_time,
                # Agent
                agent_response=agent_response,
                agent_intent=agent_intent,
                agent_agent=agent_agent,
                # TTS
                audio_data=tts_result.audio_data,
                audio_format=tts_result.format,
                audio_duration_seconds=tts_result.duration_seconds,
                tts_processing_time_ms=tts_time,
                # Total
                total_processing_time_ms=total_time,
            )

        except Exception as e:
            self._stats["failed"] += 1
            total_time = (time.monotonic() - total_start) * 1000

            logger.error(
                "voice.pipeline_failed",
                error=str(e),
                processing_time_ms=round(total_time, 2),
            )
            raise

    async def transcribe_only(
        self,
        audio_data: bytes,
        language: ASRLanguage = ASRLanguage.ARABIC,
        filename: str = "audio.wav",
    ) -> ASRResult:
        """
        Transcribe audio without agent processing or TTS.

        Useful for voice-to-text only mode.
        """
        return await self._asr.transcribe(
            audio_data=audio_data,
            language=language,
            filename=filename,
        )

    async def synthesize_only(
        self,
        text: str,
        voice: str = "tara",
        speed: float = 1.0,
    ) -> TTSResult:
        """
        Synthesize text without ASR or agent processing.

        Useful for text-to-speech only mode.
        """
        return await self._tts.synthesize(
            text=text,
            voice=voice,
            speed=speed,
        )

    def get_stats(self) -> dict[str, Any]:
        """Get pipeline statistics."""
        return {
            **self._stats,
            "success_rate": (
                self._stats["successful"] / self._stats["total_requests"]
                if self._stats["total_requests"] > 0 else 0
            ),
        }

    def _update_avg_time(self, new_time_ms: float) -> None:
        """Update rolling average processing time."""
        count = self._stats["successful"]
        if count > 0:
            current_avg = self._stats["avg_total_time_ms"]
            self._stats["avg_total_time_ms"] = (
                (current_avg * (count - 1) + new_time_ms) / count
            )
