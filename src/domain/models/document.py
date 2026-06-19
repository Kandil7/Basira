"""
Domain data models for document processing.

Used by the Internal Ops Agent for report summarization and RAG storage.
"""

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class DocumentChunk(BaseModel):
    """A chunk of text stored in the vector store."""

    chunk_id: str = Field(..., description="Unique chunk identifier")
    content: str = Field(..., description="Text content of the chunk")
    metadata: dict = Field(default_factory=dict, description="Source metadata")
    embedding: list[float] | None = Field(None, description="Vector embedding")
    document_id: str = Field(..., description="Parent document ID")
    chunk_index: int = Field(..., description="Position within document")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ReportSummary(BaseModel):
    """Summary of an uploaded report."""

    document_id: str
    filename: str
    summary_type: str = Field(description="full, kpi_extraction, task_generation")
    summary: str = Field(..., description="Generated summary text")
    kpis: list[dict] = Field(default_factory=list, description="Extracted KPIs")
    tasks: list[dict] = Field(default_factory=list, description="Generated tasks")
    language: str = "ar"
    chunk_count: int = Field(description="Number of chunks stored in Qdrant")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class IngestRequest(BaseModel):
    """Request to ingest a document into the vector store."""

    content: str = Field(..., description="Document text content")
    filename: str = Field(..., description="Original filename")
    metadata: dict = Field(default_factory=dict, description="Additional metadata")
    chunk_size: int = Field(default=1000, description="Characters per chunk")
    chunk_overlap: int = Field(default=200, description="Overlap between chunks")
