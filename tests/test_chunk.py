"""Tests for text chunking."""

from research_pipeline.paper.chunk import chunk_text, needs_chunking


def test_short_text_no_chunking():
    assert not needs_chunking("short text")
    assert chunk_text("short text") == ["short text"]


def test_long_text_needs_chunking():
    long_text = "a" * 100_000
    assert needs_chunking(long_text)


def test_chunks_have_overlap():
    long_text = "word " * 20_000  # ~100K chars
    chunks = chunk_text(long_text)
    assert len(chunks) > 1
    # Each chunk should be under the chunk size (with some tolerance)
    for chunk in chunks:
        assert len(chunk) <= 65_000


def test_empty_text():
    assert not needs_chunking("")
    assert chunk_text("") == [""]
