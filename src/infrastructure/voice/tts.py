"""
TTS (Text-to-Speech) — text-to-speech using Groq Orpheus.

Converts Arabic (and English) text to natural-sounding speech using
Groq's Canopy Labs Orpheus models.
"""

import asyncio
import io
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class TTSVoice(Enum):
    """Orpheus voice options."""
    # Arabic voices
    ARABIC_SAUDI = "arabic-saudi"
    # English voices (fallback)
    ENGLISH_DEFAULT = "english"


class TTSFormat(Enum):
    """Audio output formats."""
    MP3 = "mp3"
    WAV = "wav"
    OPUS = "opus"
    AAC = "aac"
    FLAC = "flac"


@dataclass
class TTSResult:
    """Result from text-to-speech synthesis."""
    audio_data: bytes
    format: str
    duration_seconds: float
    processing_time_ms: float
    model: str
    voice: str
    text_length: int
    sample_rate: int = 24000

    @property
    def size_bytes(self) -> int:
        """Size of audio data in bytes."""
        return len(self.audio_data)

    @property
    def size_mb(self) -> float:
        """Size of audio data in MB."""
        return self.size_bytes / (1024 * 1024)


class SpeechSynthesizer:
    """
    Text-to-speech using Groq's Canopy Labs Orpheus models.

    Supports:
    - Arabic speech synthesis (Saudi dialect)
    - Multiple voice options
    - Various output formats
    - SSML support for prosody control
    """

    # Orpheus model options
    MODEL_ORPHEUS_ENGLISH = "canopylabs/orpheus-v1-english"
    MODEL_ORPHEUS_ARABIC = "canopylabs/orpheus-arabic-saudi"

    # Voice presets for Orpheus
    VOICE_PRESETS = {
        "default": "tara",
        "arabic": "tara",
        "friendly": "tara",
        "professional": "tara",
    }

    def __init__(
        self,
        api_key: str,
        model: str = "canopylabs/orpheus-arabic-saudi",
        base_url: str = "https://api.groq.com/openai/v1",
    ) -> None:
        """
        Initialize speech synthesizer.

        Args:
            api_key: Groq API key
            model: Orpheus model to use
            base_url: Groq API base URL
        """
        self._api_key = api_key
        self._model = model
        self._base_url = base_url
        self._client = None

        self._init_client()
        logger.info(
            "tts.initialized",
            model=model,
            base_url=base_url,
        )

    def _init_client(self) -> None:
        """Initialize OpenAI-compatible client for Groq."""
        try:
            import openai
            self._client = openai.AsyncOpenAI(
                api_key=self._api_key,
                base_url=self._base_url,
            )
        except ImportError:
            logger.error("tts.missing_openai_dep")
        except Exception as e:
            logger.error("tts.client_init_failed", error=str(e))

    async def synthesize(
        self,
        text: str,
        voice: str = "tara",
        response_format: TTSFormat = TTSFormat.MP3,
        speed: float = 1.0,
    ) -> TTSResult:
        """
        Synthesize text to speech.

        Args:
            text: Text to convert to speech
            voice: Voice preset (tara for Arabic)
            response_format: Output audio format
            speed: Speech speed (0.25 to 4.0)

        Returns:
            TTSResult with audio data and metadata.
        """
        if not self._client:
            raise RuntimeError("TTS client not initialized. Check GROQ_API_KEY.")

        # Validate text length (Orpheus has limits)
        if len(text) > 10000:
            raise ValueError(f"Text too long: {len(text)} chars (max: 10000)")

        # Clamp speed
        speed = max(0.25, min(4.0, speed))

        start = time.monotonic()

        try:
            # Call Groq Orpheus API
            response = await self._client.audio.speech.create(
                model=self._model,
                voice=voice,
                input=text,
                response_format=response_format.value,
                speed=speed,
            )

            # Read audio data
            audio_data = await response.aread()

            processing_time = (time.monotonic() - start) * 1000

            # Estimate duration (rough: ~24KB per second for MP3)
            estimated_duration = len(audio_data) / 24000 if response_format == TTSFormat.MP3 else 0

            result = TTSResult(
                audio_data=audio_data,
                format=response_format.value,
                duration_seconds=estimated_duration,
                processing_time_ms=processing_time,
                model=self._model,
                voice=voice,
                text_length=len(text),
            )

            logger.info(
                "tts.synthesis_success",
                voice=voice,
                text_length=len(text),
                audio_size=result.size_bytes,
                processing_time_ms=round(processing_time, 2),
            )

            return result

        except Exception as e:
            processing_time = (time.monotonic() - start) * 1000
            logger.error(
                "tts.synthesis_failed",
                error=str(e),
                processing_time_ms=round(processing_time, 2),
            )
            raise

    async def synthesize_arabic(
        self,
        text: str,
        voice: str = "tara",
        speed: float = 1.0,
    ) -> TTSResult:
        """
        Convenience method for Arabic synthesis.

        Args:
            text: Arabic text to convert to speech
            voice: Voice preset
            speed: Speech speed

        Returns:
            TTSResult with Arabic audio.
        """
        return await self.synthesize(
            text=text,
            voice=voice,
            response_format=TTSFormat.MP3,
            speed=speed,
        )

    async def health_check(self) -> dict[str, Any]:
        """Check TTS service health."""
        return {
            "status": "healthy" if self._client else "unavailable",
            "model": self._model,
            "provider": "groq",
            "voices": list(self.VOICE_PRESETS.keys()),
        }
