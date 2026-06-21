"""
ASR (Automatic Speech Recognition) — speech-to-text using Groq Whisper.

Converts Arabic (and other language) audio to text using Groq's Whisper models.
Supports streaming, batch processing, and automatic language detection.
"""

import asyncio
import io
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class ASRLanguage(Enum):
    """Supported ASR languages."""
    ARABIC = "ar"
    ENGLISH = "en"
    AUTO = "auto"


@dataclass
class ASRResult:
    """Result from speech recognition."""
    text: str
    language: str
    confidence: float
    duration_seconds: float
    processing_time_ms: float
    model: str
    segments: list[dict[str, Any]] = field(default_factory=list)

    @property
    def words_per_second(self) -> float:
        """Words per minute of the audio."""
        if self.duration_seconds > 0:
            return len(self.text.split()) / self.duration_seconds
        return 0


class SpeechRecognizer:
    """
    Speech-to-text using Groq's Whisper models.

    Supports:
    - Arabic speech recognition (primary)
    - Multi-language support
    - Automatic language detection
    - Timestamped segments
    - Streaming audio input
    """

    # Whisper model options
    MODEL_WHISPER_LARGE = "whisper-large-v3"
    MODEL_WHISPER_TURBO = "whisper-large-v3-turbo"

    # Supported audio formats
    SUPPORTED_FORMATS = {
        "audio/wav": "wav",
        "audio/mp3": "mp3",
        "audio/mpeg": "mp3",
        "audio/ogg": "ogg",
        "audio/flac": "flac",
        "audio/webm": "webm",
        "audio/mp4": "m4a",
        "audio/x-m4a": "m4a",
    }

    # Max file size (25MB for Whisper API)
    MAX_FILE_SIZE = 25 * 1024 * 1024

    def __init__(
        self,
        api_key: str,
        model: str = "whisper-large-v3",
        base_url: str = "https://api.groq.com/openai/v1",
    ) -> None:
        """
        Initialize speech recognizer.

        Args:
            api_key: Groq API key
            model: Whisper model to use
            base_url: Groq API base URL
        """
        self._api_key = api_key
        self._model = model
        self._base_url = base_url
        self._client = None

        self._init_client()
        logger.info(
            "asr.initialized",
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
            logger.error("asr.missing_openai_dep")
        except Exception as e:
            logger.error("asr.client_init_failed", error=str(e))

    async def transcribe(
        self,
        audio_data: bytes,
        language: ASRLanguage = ASRLanguage.AUTO,
        filename: str = "audio.wav",
        response_format: str = "verbose_json",
        temperature: float = 0.0,
    ) -> ASRResult:
        """
        Transcribe audio to text.

        Args:
            audio_data: Raw audio bytes
            language: Language hint (Arabic, English, or auto-detect)
            filename: Original filename (for format detection)
            response_format: Response format (json, verbose_json, text, srt, vtt)
            temperature: Sampling temperature (0.0 for deterministic)

        Returns:
            ASRResult with transcribed text and metadata.
        """
        if not self._client:
            raise RuntimeError("ASR client not initialized. Check GROQ_API_KEY.")

        # Validate file size
        if len(audio_data) > self.MAX_FILE_SIZE:
            raise ValueError(f"Audio file too large: {len(audio_data)} bytes (max: {self.MAX_FILE_SIZE})")

        # Detect format from filename
        format_ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "wav"

        start = time.monotonic()

        try:
            # Build language prompt
            language_prompt = None
            if language == ASRLanguage.ARABIC:
                language_prompt = "arabic"
            elif language == ASRLanguage.ENGLISH:
                language_prompt = "english"

            # Create file-like object for API
            audio_file = io.BytesIO(audio_data)
            audio_file.name = filename

            # Call Groq Whisper API
            response = await self._client.audio.transcriptions.create(
                model=self._model,
                file=audio_file,
                language=language_prompt if language != ASRLanguage.AUTO else None,
                response_format=response_format,
                temperature=temperature,
            )

            processing_time = (time.monotonic() - start) * 1000

            # Parse response
            if response_format == "verbose_json":
                result = ASRResult(
                    text=response.text,
                    language=getattr(response, "language", "unknown"),
                    confidence=getattr(response, "avg_logprob", 0.0),
                    duration_seconds=getattr(response, "duration", 0.0),
                    processing_time_ms=processing_time,
                    model=self._model,
                    segments=[
                        {
                            "start": seg.get("start", 0),
                            "end": seg.get("end", 0),
                            "text": seg.get("text", ""),
                        }
                        for seg in getattr(response, "segments", [])
                    ],
                )
            else:
                # Simple text response
                text = response if isinstance(response, str) else response.text
                result = ASRResult(
                    text=text,
                    language="unknown",
                    confidence=0.0,
                    duration_seconds=0.0,
                    processing_time_ms=processing_time,
                    model=self._model,
                )

            logger.info(
                "asr.transcription_success",
                language=result.language,
                duration=result.duration_seconds,
                text_length=len(result.text),
                processing_time_ms=round(processing_time, 2),
            )

            return result

        except Exception as e:
            processing_time = (time.monotonic() - start) * 1000
            logger.error(
                "asr.transcription_failed",
                error=str(e),
                processing_time_ms=round(processing_time, 2),
            )
            raise

    async def transcribe_arabic(
        self,
        audio_data: bytes,
        filename: str = "audio.wav",
    ) -> ASRResult:
        """
        Convenience method for Arabic transcription.

        Args:
            audio_data: Raw audio bytes
            filename: Original filename

        Returns:
            ASRResult with Arabic transcription.
        """
        return await self.transcribe(
            audio_data=audio_data,
            language=ASRLanguage.ARABIC,
            filename=filename,
        )

    async def health_check(self) -> dict[str, Any]:
        """Check ASR service health."""
        return {
            "status": "healthy" if self._client else "unavailable",
            "model": self._model,
            "provider": "groq",
            "max_file_size_mb": self.MAX_FILE_SIZE // (1024 * 1024),
            "supported_formats": list(self.SUPPORTED_FORMATS.keys()),
        }
