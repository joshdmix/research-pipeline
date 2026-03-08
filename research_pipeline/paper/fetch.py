"""arxiv API wrapper and PDF download."""

from __future__ import annotations

from pathlib import Path

import arxiv
import structlog

from research_pipeline.models import PaperCandidate

log = structlog.get_logger()


def search_arxiv(query: str, max_results: int = 50) -> list[PaperCandidate]:
    """Search arxiv for papers matching a query."""
    client = arxiv.Client()
    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.Relevance,
    )

    candidates = []
    for result in client.results(search):
        candidate = PaperCandidate(
            arxiv_id=result.entry_id.split("/abs/")[-1],
            title=result.title,
            abstract=result.summary,
            authors=[a.name for a in result.authors],
            published=result.published.isoformat() if result.published else "",
        )
        candidates.append(candidate)

    log.info("arxiv_search_complete", query=query, results=len(candidates))
    return candidates


def download_paper(arxiv_id: str, cache_dir: Path) -> Path:
    """Download a paper PDF from arxiv. Returns path to the PDF."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    safe_id = arxiv_id.replace("/", "_")
    pdf_path = cache_dir / f"{safe_id}.pdf"

    if pdf_path.exists():
        log.info("paper_cached", arxiv_id=arxiv_id, path=str(pdf_path))
        return pdf_path

    client = arxiv.Client()
    search = arxiv.Search(id_list=[arxiv_id])
    paper = next(client.results(search))
    paper.download_pdf(dirpath=str(cache_dir), filename=pdf_path.name)

    log.info("paper_downloaded", arxiv_id=arxiv_id, path=str(pdf_path))
    return pdf_path
