"""
Embedding providers — abstraction layer for multiple embedding APIs.

Each provider implements the same interface, making it easy to swap
between OpenAI, Jina, Voyage, or local models.
"""

from abc import ABC, abstractmethod
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class EmbeddingProvider(ABC):
    """Abstract embedding provider interface."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name for logging."""
        ...

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Embedding vector dimension."""
        ...

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        ...

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if provider is available."""
        ...


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """
    OpenAI embedding provider.

    Works with OpenAI, Azure OpenAI, and any OpenAI-compatible API
    (Jina, Together, etc.) by specifying base_url.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-3-small",
        base_url: str | None = None,
        dimensions: int | None = None,
    ) -> None:
        import openai

        self._model = model
        self._dimensions = dimensions or 1536
        self._client = openai.AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
        )
        logger.info(
            "embedding.openai_init",
            model=model,
            base_url=base_url or "api.openai.com",
            dimensions=self._dimensions,
        )

    @property
    def name(self) -> str:
        return "openai"

    @property
    def dimension(self) -> int:
        return self._dimensions

    async def embed(self, text: str) -> list[float]:
        """Generate embedding via OpenAI API."""
        response = await self._client.embeddings.create(
            model=self._model,
            input=text[:8000],  # Truncate for token limits
            dimensions=self._dimensions,
        )
        return response.data[0].embedding

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts."""
        if not texts:
            return []

        # OpenAI supports batch embedding (up to 2048 texts per request)
        truncated = [t[:8000] for t in texts]
        response = await self._client.embeddings.create(
            model=self._model,
            input=truncated,
            dimensions=self._dimensions,
        )
        return [item.embedding for item in response.data]

    async def health_check(self) -> bool:
        """Check OpenAI API availability."""
        try:
            await self.embed("health check")
            return True
        except Exception as e:
            logger.error("embedding.openai_health_check_failed", error=str(e))
            return False


class JinaEmbeddingProvider(EmbeddingProvider):
    """
    Jina AI embedding provider.

    Excellent for multilingual text including Arabic.
    Uses Jina's API which is OpenAI-compatible.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "jina-embeddings-v3",
        dimensions: int = 1024,
    ) -> None:
        import openai

        self._model = model
        self._dimensions = dimensions
        self._client = openai.AsyncOpenAI(
            api_key=api_key,
            base_url="https://api.jina.ai/v1",
        )
        logger.info(
            "embedding.jina_init",
            model=model,
            dimensions=dimensions,
        )

    @property
    def name(self) -> str:
        return "jina"

    @property
    def dimension(self) -> int:
        return self._dimensions

    async def embed(self, text: str) -> list[float]:
        """Generate embedding via Jina API."""
        response = await self._client.embeddings.create(
            model=self._model,
            input=text[:8000],
        )
        return response.data[0].embedding

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts."""
        if not texts:
            return []

        truncated = [t[:8000] for t in texts]
        response = await self._client.embeddings.create(
            model=self._model,
            input=truncated,
        )
        return [item.embedding for item in response.data]

    async def health_check(self) -> bool:
        """Check Jina API availability."""
        try:
            await self.embed("health check")
            return True
        except Exception as e:
            logger.error("embedding.jina_health_check_failed", error=str(e))
            return False


class SentenceTransformerProvider(EmbeddingProvider):
    """
    Local sentence-transformers embedding provider.

    Runs locally without API calls. Good for:
    - Development/testing
    - Offline environments
    - Cost-sensitive deployments

    Uses all-MiniLM-L6-v2 (384 dimensions) by default.
    """

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        device: str = "cpu",
    ) -> None:
        self._model_name = model_name
        self._device = device
        self._model = None
        self._dimension = 384  # Default for MiniLM

        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(model_name, device=device)
            # Get actual dimension from model
            self._dimension = self._model.get_sentence_embedding_dimension()
            logger.info(
                "embedding.local_init",
                model=model_name,
                device=device,
                dimension=self._dimension,
            )
        except ImportError:
            logger.error(
                "embedding.local_import_error",
                message="sentence-transformers not installed. Run: pip install sentence-transformers",
            )
        except Exception as e:
            logger.error("embedding.local_init_failed", error=str(e))

    @property
    def name(self) -> str:
        return "local"

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed(self, text: str) -> list[float]:
        """Generate embedding using local model."""
        if self._model is None:
            raise RuntimeError("Local embedding model not initialized")

        # sentence-transformers is sync, run in thread pool
        import asyncio
        loop = asyncio.get_event_loop()
        embedding = await loop.run_in_executor(
            None,
            lambda: self._model.encode(text, show_progress_bar=False),
        )
        return embedding.tolist()

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts."""
        if self._model is None:
            raise RuntimeError("Local embedding model not initialized")

        import asyncio
        loop = asyncio.get_event_loop()
        embeddings = await loop.run_in_executor(
            None,
            lambda: self._model.encode(texts, show_progress_bar=False, batch_size=64),
        )
        return [emb.tolist() for emb in embeddings]

    async def health_check(self) -> bool:
        """Check if local model is loaded."""
        return self._model is not None


class PlaceholderProvider(EmbeddingProvider):
    """
    Placeholder embedding provider for development/testing.

    Generates deterministic but NOT semantically meaningful vectors.
    Used when no real embedding provider is configured.
    """

    DIMENSION = 1536

    @property
    def name(self) -> str:
        return "placeholder"

    @property
    def dimension(self) -> int:
        return self.DIMENSION

    async def embed(self, text: str) -> list[float]:
        """Generate deterministic placeholder embedding."""
        import hashlib
        import struct

        h = hashlib.sha512(text.encode("utf-8")).digest()
        vec: list[float] = []
        for i in range(0, min(len(h), self.DIMENSION * 4), 4):
            chunk = h[i : i + 4] if i + 4 <= len(h) else h[i:].ljust(4, b"\x00")
            val = struct.unpack(">f", chunk)[0]
            val = max(-1.0, min(1.0, val / 1e38))
            vec.append(val)
        while len(vec) < self.DIMENSION:
            vec.append(0.0)
        return vec[:self.DIMENSION]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate placeholder embeddings for a batch."""
        return [await self.embed(t) for t in texts]

    async def health_check(self) -> bool:
        """Always healthy."""
        return True
