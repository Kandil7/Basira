"""
Voice infrastructure tests — ASR, TTS, and pipeline.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.infrastructure.voice.asr import SpeechRecognizer, ASRResult, ASRLanguage
from src.infrastructure.voice.tts import SpeechSynthesizer, TTSResult, TTSFormat
from src.infrastructure.voice.pipeline import VoicePipeline, VoiceRequest, VoiceResponse


class TestASRResult:
    """Test ASRResult dataclass."""

    def test_basic_result(self):
        result = ASRResult(
            text="مرحبا كيف حالك",
            language="ar",
            confidence=0.95,
            duration_seconds=3.5,
            processing_time_ms=150.0,
            model="whisper-large-v3",
        )
        assert result.text == "مرحبا كيف حالك"
        assert result.language == "ar"
        assert result.confidence == 0.95
        assert result.duration_seconds == 3.5

    def test_words_per_second(self):
        result = ASRResult(
            text="hello world test",
            language="en",
            confidence=0.9,
            duration_seconds=2.0,
            processing_time_ms=100.0,
            model="whisper-large-v3",
        )
        assert result.words_per_second == 1.5  # 3 words / 2 seconds

    def test_words_per_second_zero_duration(self):
        result = ASRResult(
            text="hello",
            language="en",
            confidence=0.9,
            duration_seconds=0.0,
            processing_time_ms=100.0,
            model="whisper-large-v3",
        )
        assert result.words_per_second == 0


class TestTTSResult:
    """Test TTSResult dataclass."""

    def test_basic_result(self):
        result = TTSResult(
            audio_data=b"fake audio data",
            format="mp3",
            duration_seconds=2.5,
            processing_time_ms=200.0,
            model="canopylabs/orpheus-arabic-saudi",
            voice="tara",
            text_length=50,
        )
        assert result.audio_data == b"fake audio data"
        assert result.format == "mp3"
        assert result.size_bytes == 15  # len(b"fake audio data")

    def test_size_mb(self):
        result = TTSResult(
            audio_data=b"x" * (1024 * 1024),  # 1 MB
            format="mp3",
            duration_seconds=1.0,
            processing_time_ms=100.0,
            model="test",
            voice="tara",
            text_length=10,
        )
        assert result.size_mb == pytest.approx(1.0)


class TestSpeechRecognizer:
    """Test SpeechRecognizer with mocked client."""

    def setup_method(self):
        self.recognizer = SpeechRecognizer(
            api_key="test_key",
            model="whisper-large-v3",
        )

    def test_initialization(self):
        assert self.recognizer._model == "whisper-large-v3"
        assert self.recognizer._api_key == "test_key"

    @pytest.mark.asyncio
    async def test_health_check_no_client(self):
        self.recognizer._client = None
        health = await self.recognizer.health_check()
        assert health["status"] == "unavailable"

    @pytest.mark.asyncio
    async def test_health_check_with_client(self):
        self.recognizer._client = MagicMock()
        health = await self.recognizer.health_check()
        assert health["status"] == "healthy"
        assert health["model"] == "whisper-large-v3"


class TestSpeechSynthesizer:
    """Test SpeechSynthesizer with mocked client."""

    def setup_method(self):
        self.synthesizer = SpeechSynthesizer(
            api_key="test_key",
            model="canopylabs/orpheus-arabic-saudi",
        )

    def test_initialization(self):
        assert self.synthesizer._model == "canopylabs/orpheus-arabic-saudi"
        assert self.synthesizer._api_key == "test_key"

    @pytest.mark.asyncio
    async def test_health_check_no_client(self):
        self.synthesizer._client = None
        health = await self.synthesizer.health_check()
        assert health["status"] == "unavailable"

    @pytest.mark.asyncio
    async def test_health_check_with_client(self):
        self.synthesizer._client = MagicMock()
        health = await self.synthesizer.health_check()
        assert health["status"] == "healthy"
        assert health["model"] == "canopylabs/orpheus-arabic-saudi"


class TestVoicePipeline:
    """Test VoicePipeline with mocked ASR/TTS."""

    def setup_method(self):
        self.mock_asr = AsyncMock()
        self.mock_tts = AsyncMock()
        self.mock_agent = AsyncMock()

        self.pipeline = VoicePipeline(
            asr=self.mock_asr,
            tts=self.mock_tts,
            agent_fn=self.mock_agent,
        )

    @pytest.mark.asyncio
    async def test_process_success(self):
        # Mock ASR result
        self.mock_asr.transcribe.return_value = ASRResult(
            text="ما هي مبيعات اليوم؟",
            language="ar",
            confidence=0.95,
            duration_seconds=2.0,
            processing_time_ms=150.0,
            model="whisper-large-v3",
        )

        # Mock agent result
        self.mock_agent.return_value = {
            "response": "مبيعات اليوم 45,000 ريال",
            "intent": "analytics",
            "agent": "analytical",
        }

        # Mock TTS result
        self.mock_tts.synthesize.return_value = TTSResult(
            audio_data=b"fake audio",
            format="mp3",
            duration_seconds=3.0,
            processing_time_ms=200.0,
            model="canopylabs/orpheus-arabic-saudi",
            voice="tara",
            text_length=30,
        )

        # Process
        request = VoiceRequest(
            audio_data=b"fake audio data",
            filename="test.wav",
        )
        result = await self.pipeline.process(request)

        # Assertions
        assert result.transcribed_text == "ما هي مبيعات اليوم؟"
        assert result.agent_response == "مبيعات اليوم 45,000 ريال"
        assert result.agent_intent == "analytics"
        assert result.audio_data == b"fake audio"
        assert result.total_processing_time_ms >= 0

    @pytest.mark.asyncio
    async def test_transcribe_only(self):
        self.mock_asr.transcribe.return_value = ASRResult(
            text="test transcription",
            language="en",
            confidence=0.9,
            duration_seconds=1.0,
            processing_time_ms=100.0,
            model="whisper-large-v3",
        )

        result = await self.pipeline.transcribe_only(b"audio data")
        assert result.text == "test transcription"

    @pytest.mark.asyncio
    async def test_synthesize_only(self):
        self.mock_tts.synthesize.return_value = TTSResult(
            audio_data=b"audio",
            format="mp3",
            duration_seconds=1.0,
            processing_time_ms=100.0,
            model="test",
            voice="tara",
            text_length=10,
        )

        result = await self.pipeline.synthesize_only("hello world")
        assert result.audio_data == b"audio"

    def test_stats(self):
        stats = self.pipeline.get_stats()
        assert "total_requests" in stats
        assert "successful" in stats
        assert "failed" in stats
        assert "success_rate" in stats


class TestVoiceRequest:
    """Test VoiceRequest dataclass."""

    def test_default_values(self):
        request = VoiceRequest(audio_data=b"test")
        assert request.language == ASRLanguage.ARABIC
        assert request.voice == "tara"
        assert request.speed == 1.0
        assert request.metadata == {}


class TestVoiceResponse:
    """Test VoiceResponse dataclass."""

    def test_audio_size(self):
        response = VoiceResponse(
            transcribed_text="test",
            asr_language="ar",
            asr_confidence=0.9,
            asr_duration_seconds=1.0,
            asr_processing_time_ms=100.0,
            agent_response="response",
            agent_intent="analytics",
            agent_agent="analytical",
            audio_data=b"audio data",
            audio_format="mp3",
            audio_duration_seconds=2.0,
            tts_processing_time_ms=200.0,
            total_processing_time_ms=500.0,
        )
        assert response.audio_size_bytes == 10  # len(b"audio data")
