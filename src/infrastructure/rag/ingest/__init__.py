"""
RAG ingest pipeline — document ingestion into Qdrant.

Phase 2 stubs for policies, FAQs, and internal docs ingestion.
Production implementation will handle PDF/Excel parsing and chunking.
"""

from src.domain.interfaces.vector_store import VectorStoreInterface


class DocumentIngester:
    """
    Ingests documents into Qdrant for RAG retrieval.

    Phase 2: Stub implementation with TODO markers.
    Phase 3: Full PDF/Excel parsing, chunking, and embedding.
    """

    def __init__(self, vector_store: VectorStoreInterface) -> None:
        self._vector_store = vector_store

    async def ingest_text(
        self,
        text: str,
        collection: str = "company_docs",
        metadata: dict | None = None,
    ) -> str:
        """
        Ingest raw text into the vector store.

        TODO: Implement chunking strategy (1000 chars, 200 overlap).
        TODO: Generate embeddings via embedding service.
        TODO: Upsert chunks with metadata to Qdrant.

        Args:
            text: Raw document text
            collection: Target Qdrant collection
            metadata: Source metadata (filename, page, section)

        Returns:
            Document ID for the ingested content.
        """
        # TODO: Implement chunking
        # chunks = chunk_text(text, chunk_size=1000, overlap=200)

        # TODO: Generate embeddings for each chunk
        # embeddings = await embed_chunks(chunks)

        # TODO: Upsert to Qdrant
        # await self._vector_store.upsert(collection, points)

        raise NotImplementedError(
            "DocumentIngester.ingest_text is a Phase 2 stub. "
            "Implement chunking + embedding + Qdrant upsert."
        )

    async def ingest_file(
        self,
        file_path: str,
        collection: str = "company_docs",
    ) -> str:
        """
        Ingest a file (PDF, Excel, TXT) into the vector store.

        TODO: Detect file type and extract text.
        TODO: For PDF → use pypdf or pdfplumber.
        TODO: For Excel → use openpyxl.
        TODO: For TXT → read directly.

        Args:
            file_path: Path to the file
            collection: Target Qdrant collection

        Returns:
            Document ID.
        """
        raise NotImplementedError(
            "DocumentIngester.ingest_file is a Phase 2 stub. "
            "Implement file type detection + text extraction."
        )

    async def ingest_policies(self, policies_dir: str) -> int:
        """
        Bulk-ingest all policy documents from a directory.

        TODO: Walk directory for .pdf, .txt, .md files.
        TODO: Ingest each file.
        TODO: Return count of ingested documents.

        Args:
            policies_dir: Path to policies directory

        Returns:
            Number of documents ingested.
        """
        # TODO: Implement bulk ingestion
        return 0

    async def ingest_faqs(self, faq_data: list[dict]) -> int:
        """
        Ingest FAQ entries from structured data.

        TODO: Accept list of {question, answer} dicts.
        TODO: Chunk and ingest each Q&A pair.

        Args:
            faq_data: List of FAQ entries

        Returns:
            Number of FAQ entries ingested.
        """
        # TODO: Implement FAQ ingestion
        return 0
