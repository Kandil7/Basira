"""Infrastructure layer — external integrations."""

from src.infrastructure.data.odoo_client import OdooClient
from src.infrastructure.rag.vectorstore import QdrantVectorStore

__all__ = ["OdooClient", "QdrantVectorStore"]
