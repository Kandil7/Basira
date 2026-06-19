"""
Document domain service.

Handles document ingestion, chunking, storage in Qdrant, and
summarization for the Internal Ops Agent.
"""

import hashlib
import uuid
from datetime import datetime, timezone

from src.domain.interfaces.vector_store import VectorStoreInterface
from src.domain.models.document import (
    DocumentChunk,
    IngestRequest,
    ReportSummary,
)


class DocumentService:
    """Business logic for document processing and RAG storage."""

    CHUNK_SIZE_DEFAULT = 1000
    CHUNK_OVERLAP_DEFAULT = 200

    def __init__(self, vector_store: VectorStoreInterface) -> None:
        self._vector_store = vector_store

    def _chunk_text(
        self,
        text: str,
        chunk_size: int = CHUNK_SIZE_DEFAULT,
        chunk_overlap: int = CHUNK_OVERLAP_DEFAULT,
    ) -> list[str]:
        """
        Split text into overlapping chunks.

        Args:
            text: Full document text
            chunk_size: Maximum characters per chunk
            chunk_overlap: Overlap between consecutive chunks

        Returns:
            List of text chunks.
        """
        chunks: list[str] = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]
            chunks.append(chunk)
            start += chunk_size - chunk_overlap
        return chunks

    def _generate_chunk_id(self, document_id: str, index: int) -> str:
        """Generate deterministic chunk ID."""
        raw = f"{document_id}:chunk:{index}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    async def ingest_document(
        self,
        request: IngestRequest,
        collection_name: str = "company_docs",
    ) -> ReportSummary:
        """
        Ingest a document into the vector store.

        Chunks the text, stores each chunk with metadata, and returns
        a summary object.

        Args:
            request: Ingestion request with content and metadata
            collection_name: Target Qdrant collection

        Returns:
            ReportSummary with chunk count and document ID.
        """
        document_id = f"doc_{uuid.uuid4().hex[:12]}"

        chunks = self._chunk_text(
            request.content,
            request.chunk_size,
            request.chunk_overlap,
        )

        points: list[dict] = []
        for idx, chunk_text in enumerate(chunks):
            chunk_id = self._generate_chunk_id(document_id, idx)
            points.append(
                {
                    "id": chunk_id,
                    "vector": [0.0] * 1536,  # Placeholder — embeddings added by retriever
                    "payload": {
                        "content": chunk_text,
                        "document_id": document_id,
                        "chunk_index": idx,
                        "filename": request.filename,
                        "metadata": request.metadata,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    },
                }
            )

        await self._vector_store.upsert(collection_name, points)

        return ReportSummary(
            document_id=document_id,
            filename=request.filename,
            summary_type="full",
            summary=f"Ingested {len(chunks)} chunks from {request.filename}",
            chunk_count=len(chunks),
        )

    async def search_documents(
        self,
        query: str,
        collection_name: str = "company_docs",
        limit: int = 5,
    ) -> list[DocumentChunk]:
        """
        Search for relevant document chunks.

        Args:
            query: Search query text
            collection_name: Collection to search
            limit: Maximum results

        Returns:
            List of matching DocumentChunk objects.
        """
        # NOTE: In production, the query is first embedded via OpenAI,
        # then passed as query_vector. Here we use a placeholder.
        results = await self._vector_store.search(
            collection_name=collection_name,
            query_vector=[0.0] * 1536,  # Placeholder — real vector from embedding service
            limit=limit,
        )

        chunks: list[DocumentChunk] = []
        for r in results:
            payload = r.get("payload", {})
            chunks.append(
                DocumentChunk(
                    chunk_id=r.get("id", ""),
                    content=payload.get("content", ""),
                    metadata=payload.get("metadata", {}),
                    document_id=payload.get("document_id", ""),
                    chunk_index=payload.get("chunk_index", 0),
                )
            )

        return chunks
