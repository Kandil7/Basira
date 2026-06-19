"""
RAG ingest pipeline — document ingestion into Qdrant.

Handles chunking, embedding, and storage of documents for RAG retrieval.
Supports text, PDF, Excel, and FAQ data ingestion.
"""

import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog

from src.domain.interfaces.vector_store import VectorStoreInterface
from src.infrastructure.rag.ingest.chunking import chunk_text, chunk_by_paragraphs

logger = structlog.get_logger(__name__)


class DocumentIngester:
    """
    Ingests documents into Qdrant for RAG retrieval.

    Handles the full pipeline: text extraction → chunking → embedding → storage.
    """

    CHUNK_SIZE = 1000
    CHUNK_OVERLAP = 200

    def __init__(
        self,
        vector_store: VectorStoreInterface,
        embedding_service: Any = None,
    ) -> None:
        self._vector_store = vector_store
        self._embedding_service = embedding_service

    def _generate_chunk_id(self, document_id: str, index: int) -> str:
        """Generate deterministic chunk ID."""
        raw = f"{document_id}:chunk:{index}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    async def _embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts."""
        if self._embedding_service is not None:
            return await self._embedding_service.embed_batch(texts)

        # Fallback: use embedding service default
        from src.infrastructure.rag.embeddings import EmbeddingService
        from src.config.settings import get_settings
        service = EmbeddingService(get_settings())
        self._embedding_service = service
        return await service.embed_batch(texts)

    async def ingest_text(
        self,
        text: str,
        collection: str = "company_docs",
        metadata: dict | None = None,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
    ) -> str:
        """
        Ingest raw text into the vector store.

        Chunks the text, generates embeddings, and stores in Qdrant.

        Args:
            text: Raw document text
            collection: Target Qdrant collection
            metadata: Source metadata (filename, page, section)
            chunk_size: Characters per chunk (default: 1000)
            chunk_overlap: Overlap between chunks (default: 200)

        Returns:
            Document ID for the ingested content.
        """
        if not text or not text.strip():
            raise ValueError("Cannot ingest empty text")

        document_id = f"doc_{uuid.uuid4().hex[:12]}"
        metadata = metadata or {}

        # Chunk the text
        chunks = list(chunk_text(
            text,
            chunk_size=chunk_size or self.CHUNK_SIZE,
            overlap=chunk_overlap or self.CHUNK_OVERLAP,
        ))

        if not chunks:
            raise ValueError("No chunks generated from text")

        # Generate embeddings
        embeddings = await self._embed_texts(chunks)

        # Build Qdrant points
        points: list[dict] = []
        for idx, (chunk_text_val, embedding) in enumerate(zip(chunks, embeddings)):
            chunk_id = self._generate_chunk_id(document_id, idx)
            points.append({
                "id": chunk_id,
                "vector": embedding,
                "payload": {
                    "content": chunk_text_val,
                    "document_id": document_id,
                    "chunk_index": idx,
                    "total_chunks": len(chunks),
                    "metadata": metadata,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                },
            })

        # Upsert to Qdrant
        await self._vector_store.upsert(collection, points)

        logger.info(
            "ingest.text_success",
            document_id=document_id,
            collection=collection,
            chunks=len(chunks),
            text_length=len(text),
        )

        return document_id

    async def ingest_file(
        self,
        file_path: str,
        collection: str = "company_docs",
    ) -> str:
        """
        Ingest a file (PDF, Excel, TXT, MD) into the vector store.

        Detects file type, extracts text, and ingests.

        Args:
            file_path: Path to the file
            collection: Target Qdrant collection

        Returns:
            Document ID.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Extract text based on file type
        if path.suffix.lower() == ".pdf":
            from src.infrastructure.data.extractors import extract_text_from_pdf
            content = path.read_bytes()
            text = extract_text_from_pdf(content)
        elif path.suffix.lower() in (".xlsx", ".xls"):
            from src.infrastructure.data.extractors import extract_text_from_excel
            content = path.read_bytes()
            text = extract_text_from_excel(content)
        elif path.suffix.lower() == ".csv":
            from src.infrastructure.data.extractors import extract_text_from_csv
            content = path.read_bytes()
            text = extract_text_from_csv(content)
        else:
            # Plain text, markdown, etc.
            text = path.read_text(encoding="utf-8", errors="replace")

        metadata = {
            "filename": path.name,
            "file_path": str(path),
            "file_type": path.suffix.lower(),
        }

        return await self.ingest_text(text, collection, metadata)

    async def ingest_policies(self, policies_dir: str) -> int:
        """
        Bulk-ingest all policy documents from a directory.

        Walks the directory for .pdf, .txt, .md, .docx files and ingests each.

        Args:
            policies_dir: Path to policies directory

        Returns:
            Number of documents ingested.
        """
        dir_path = Path(policies_dir)
        if not dir_path.exists():
            logger.warning("ingest.policies_dir_not_found", path=policies_dir)
            return 0

        supported_extensions = {".pdf", ".txt", ".md", ".xlsx", ".xls", ".csv"}
        files = [
            f for f in dir_path.rglob("*")
            if f.is_file() and f.suffix.lower() in supported_extensions
        ]

        count = 0
        for file_path in files:
            try:
                await self.ingest_file(str(file_path))
                count += 1
            except Exception as e:
                logger.warning(
                    "ingest.file_failed",
                    file=str(file_path),
                    error=str(e),
                )

        logger.info("ingest.policies_complete", directory=policies_dir, count=count)
        return count

    async def ingest_faqs(self, faq_data: list[dict[str, str]]) -> int:
        """
        Ingest FAQ entries from structured data.

        Each entry should have 'question' and 'answer' keys.

        Args:
            faq_data: List of FAQ entries [{"question": "...", "answer": "..."}]

        Returns:
            Number of FAQ entries ingested.
        """
        if not faq_data:
            return 0

        document_id = f"faq_{uuid.uuid4().hex[:12]}"
        points: list[dict] = []

        # Format FAQs as text chunks
        faq_texts = []
        for i, faq in enumerate(faq_data):
            question = faq.get("question", "")
            answer = faq.get("answer", "")
            if question and answer:
                faq_texts.append(f"سؤال: {question}\nإجابة: {answer}")

        if not faq_texts:
            return 0

        # Chunk FAQ texts
        combined_text = "\n\n---\n\n".join(faq_texts)
        chunks = list(chunk_by_paragraphs(combined_text, max_chunk_size=self.CHUNK_SIZE))

        if not chunks:
            return 0

        # Generate embeddings
        embeddings = await self._embed_texts(chunks)

        # Build points
        for idx, (chunk_val, embedding) in enumerate(zip(chunks, embeddings)):
            chunk_id = self._generate_chunk_id(document_id, idx)
            points.append({
                "id": chunk_id,
                "vector": embedding,
                "payload": {
                    "content": chunk_val,
                    "document_id": document_id,
                    "chunk_index": idx,
                    "source_type": "faq",
                    "metadata": {"type": "faq", "count": len(faq_data)},
                    "created_at": datetime.now(timezone.utc).isoformat(),
                },
            })

        await self._vector_store.upsert("company_docs", points)

        logger.info(
            "ingest.faqs_success",
            document_id=document_id,
            faq_count=len(faq_data),
            chunks=len(chunks),
        )

        return len(faq_data)
