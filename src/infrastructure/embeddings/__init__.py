"""
Embeddings infrastructure — multi-provider embedding service with caching.

Supports OpenAI, Jina, Voyage, and local sentence-transformers models.
Includes Redis-backed caching and Arabic text preprocessing.
"""

from src.infrastructure.embeddings.service import EmbeddingService
from src.infrastructure.embeddings.cache import EmbeddingCache

__all__ = ["EmbeddingService", "EmbeddingCache"]
