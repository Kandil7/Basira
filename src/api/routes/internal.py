"""
Internal API routes.

Endpoints for document upload, summarization, and internal operations.
Designed for n8n and internal tool consumption.
"""

import uuid
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
import structlog

from src.domain.models.document import IngestRequest

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.post("/internal/summarize")
async def summarize_document(
    request: Request,
    file: UploadFile = File(...),
    summary_type: str = Form(default="full"),
    language: str = Form(default="ar"),
) -> dict[str, Any]:
    """
    Upload and summarize a document.

    Accepts PDF or Excel files, processes them, stores in Qdrant,
    and generates a summary with extracted KPIs and tasks.

    **For n8n**: Send as multipart/form-data with the file and options.
    """
    document_service = request.app.state.document_service

    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    # Read file content
    try:
        content_bytes = await file.read()
        # Extract text based on file type
        if file.filename.endswith(".pdf"):
            from src.infrastructure.data.extractors import extract_text_from_pdf
            text_content = extract_text_from_pdf(content_bytes)
        elif file.filename.endswith((".xlsx", ".xls")):
            from src.infrastructure.data.extractors import extract_text_from_excel
            text_content = extract_text_from_excel(content_bytes)
        elif file.filename.endswith(".csv"):
            from src.infrastructure.data.extractors import extract_text_from_csv
            text_content = extract_text_from_csv(content_bytes)
        else:
            text_content = content_bytes.decode("utf-8", errors="replace")
    except ValueError as e:
        logger.warning("summarize.extraction_failed", filename=file.filename, error=str(e))
        raise HTTPException(status_code=400, detail=f"Document extraction failed: {e}")
    except Exception as e:
        logger.error("summarize.read_failed", filename=file.filename, error=str(e))
        raise HTTPException(status_code=400, detail=f"Failed to read file: {e}")

    # Ingest into Qdrant
    try:
        ingest_request = IngestRequest(
            content=text_content,
            filename=file.filename,
            metadata={"uploaded_by": "api", "summary_type": summary_type},
        )
        summary = await document_service.ingest_document(ingest_request)

        return {
            "document_id": summary.document_id,
            "filename": summary.filename,
            "summary": summary.summary,
            "kpis": summary.kpis,
            "tasks": summary.tasks,
            "stored_in_qdrant": True,
            "chunk_count": summary.chunk_count,
        }
    except Exception as e:
        logger.error("summarize.ingest_failed", filename=file.filename, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/internal/search")
async def search_documents(
    request: Request,
    query: str = Form(...),
    collection: str = Form(default="company_docs"),
    limit: int = Form(default=5),
) -> dict[str, Any]:
    """
    Search stored documents.

    Performs semantic search across ingested documents in Qdrant.
    """
    document_service = request.app.state.document_service

    try:
        results = await document_service.search_documents(query, collection, limit)

        return {
            "query": query,
            "results_count": len(results),
            "results": [
                {
                    "chunk_id": r.chunk_id,
                    "content": r.content,
                    "document_id": r.document_id,
                    "metadata": r.metadata,
                }
                for r in results
            ],
        }
    except Exception as e:
        logger.error("search.failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
