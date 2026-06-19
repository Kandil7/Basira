"""
Text chunking utilities for RAG ingestion.

Provides overlapping text chunking strategies for document processing.
"""

from typing import Generator


def chunk_text(
    text: str,
    chunk_size: int = 1000,
    overlap: int = 200,
) -> Generator[str, None, None]:
    """
    Split text into overlapping chunks.

    Args:
        text: Full document text
        chunk_size: Maximum characters per chunk
        overlap: Overlap between consecutive chunks

    Yields:
        Text chunks.
    """
    start = 0
    while start < len(text):
        end = start + chunk_size
        yield text[start:end]
        start += chunk_size - overlap


def chunk_by_paragraphs(
    text: str,
    max_chunk_size: int = 1000,
) -> list[str]:
    """
    Split text by paragraphs, merging small ones.

    Args:
        text: Full document text
        max_chunk_size: Maximum characters per merged chunk

    Returns:
        List of text chunks.
    """
    paragraphs = text.split("\n\n")
    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        if len(current) + len(para) + 2 <= max_chunk_size:
            current = f"{current}\n\n{para}" if current else para
        else:
            if current:
                chunks.append(current)
            current = para

    if current:
        chunks.append(current)

    return chunks
