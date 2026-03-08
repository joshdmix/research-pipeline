"""Discovery agent: topic → search queries → scored paper candidates."""

from __future__ import annotations

import json
from pathlib import Path

import structlog

from research_pipeline.agent.base import Agent
from research_pipeline.agent.prompts import DISCOVERY_SYSTEM_PROMPT
from research_pipeline.budget import Budget
from research_pipeline.models import PaperCandidate
from research_pipeline.paper.fetch import search_arxiv

log = structlog.get_logger()


def run_discovery(
    topic: str,
    model: str,
    budget: Budget,
    work_dir: Path,
    max_papers: int = 10,
    min_relevance: float = 6.0,
) -> list[PaperCandidate]:
    """Discover papers related to a topic using LLM-generated search queries."""
    agent = Agent(
        model=model,
        system_prompt=DISCOVERY_SYSTEM_PROMPT,
        budget=budget,
        work_dir=work_dir,
    )

    # Step 1: Generate search queries
    result = agent.run(
        f"Generate arxiv search queries for this research topic: {topic}\n\n"
        "Return them via report_result with data.queries as a list of query strings."
    )

    queries = result.data.get("queries", [topic]) if result.data else [topic]
    if not queries:
        queries = [topic]

    # Step 2: Search arxiv with each query
    all_candidates: dict[str, PaperCandidate] = {}
    for query in queries:
        try:
            papers = search_arxiv(query, max_results=50)
            for paper in papers:
                if paper.arxiv_id not in all_candidates:
                    all_candidates[paper.arxiv_id] = paper
        except Exception as e:
            log.warning("search_query_failed", query=query, error=str(e))

    if not all_candidates:
        log.error("no_papers_found", topic=topic)
        return []

    # Step 3: Score candidates with LLM
    candidates_summary = "\n".join(
        f"- [{c.arxiv_id}] {c.title}: {c.abstract[:200]}..."
        for c in list(all_candidates.values())[:30]
    )

    score_agent = Agent(
        model=model,
        system_prompt=DISCOVERY_SYSTEM_PROMPT,
        budget=budget,
        work_dir=work_dir,
    )

    score_result = score_agent.run(
        f"Topic: {topic}\n\n"
        f"Score these papers for relevance (0-10) and implementability (0-10):\n\n"
        f"{candidates_summary}\n\n"
        "Return via report_result with data.scores as a list of objects with "
        "arxiv_id, relevance_score, and implementability_score."
    )

    # Apply scores
    if score_result.data and "scores" in score_result.data:
        for score in score_result.data["scores"]:
            arxiv_id = score.get("arxiv_id", "")
            if arxiv_id in all_candidates:
                all_candidates[arxiv_id].relevance_score = score.get("relevance_score", 0)
                all_candidates[arxiv_id].implementability_score = score.get(
                    "implementability_score", 0
                )

    # Filter and sort
    scored = [c for c in all_candidates.values() if c.relevance_score >= min_relevance]
    scored.sort(key=lambda c: c.combined_score, reverse=True)

    result_papers = scored[:max_papers]
    log.info(
        "discovery_complete",
        topic=topic,
        total_found=len(all_candidates),
        after_filter=len(result_papers),
    )
    return result_papers
