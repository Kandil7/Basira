"""
Embedding service — backward-compatible wrapper.

This module is deprecated. Use src.infrastructure.embeddings instead.
Kept for backward compatibility with existing imports.
"""

from src.infrastructure.embeddings.service import EmbeddingService  # noqa: F401
from src.infrastructure.embeddings.providers import PlaceholderProvider  # noqa: F401

__all__ = ["EmbeddingService", "PlaceholderProvider"]
