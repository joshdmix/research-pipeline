"""Text chunking for long papers that exceed context limits."""

from __future__ import annotations

CHUNK_SIZE = 60_000
OVERLAP = 5_000
CHUNK_THRESHOLD = 80_000


def needs_chunking(text: str) -> bool:
    """Check if text is long enough to require chunking."""
    return len(text) > CHUNK_THRESHOLD


def chunk_text(text: str) -> list[str]:
    """Split text into overlapping chunks for sequential processing."""
    if not needs_chunking(text):
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + CHUNK_SIZE
        # Try to break at a paragraph boundary
        if end < len(text):
            newline_pos = text.rfind("\n\n", start + CHUNK_SIZE - 2000, end)
            if newline_pos > start:
                end = newline_pos + 2
        chunk = text[start:end]
        chunks.append(chunk)
        start = end - OVERLAP

    return chunks
