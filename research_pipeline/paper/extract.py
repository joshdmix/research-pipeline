"""PDF text extraction using PyMuPDF."""

from __future__ import annotations

from pathlib import Path

import pymupdf
import structlog

from research_pipeline.models import PaperText

log = structlog.get_logger()


def extract_paper_text(pdf_path: Path, arxiv_id: str = "") -> PaperText:
    """Extract text content from a PDF file."""
    doc = pymupdf.open(str(pdf_path))
    sections = []
    for page in doc:
        text = page.get_text("text")
        sections.append(text)
    doc.close()

    full_text = "\n\n".join(sections)
    paper_text = PaperText(
        raw_text=full_text,
        page_count=len(sections),
        char_count=len(full_text),
        arxiv_id=arxiv_id,
    )

    log.info(
        "paper_extracted",
        arxiv_id=arxiv_id,
        pages=paper_text.page_count,
        chars=paper_text.char_count,
    )
    return paper_text
