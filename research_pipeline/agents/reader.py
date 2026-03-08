"""Reader agent: paper text → structured analysis with algorithm specs."""

from __future__ import annotations

from pathlib import Path

import structlog

from research_pipeline.agent.base import Agent
from research_pipeline.agent.prompts import READER_SYSTEM_PROMPT
from research_pipeline.budget import Budget
from research_pipeline.models import AlgorithmSpec, PaperAnalysis, PaperText
from research_pipeline.paper.chunk import chunk_text, needs_chunking

log = structlog.get_logger()


def run_reader(
    paper: PaperText,
    topic: str,
    model: str,
    budget: Budget,
    work_dir: Path,
) -> PaperAnalysis | None:
    """Analyze a paper and extract algorithm specifications."""
    agent = Agent(
        model=model,
        system_prompt=READER_SYSTEM_PROMPT,
        budget=budget,
        work_dir=work_dir,
    )

    if needs_chunking(paper.raw_text):
        return _read_chunked(agent, paper, topic)

    result = agent.run(
        f"Research topic: {topic}\n\n"
        f"Paper (arxiv ID: {paper.arxiv_id}):\n\n{paper.raw_text}"
    )

    if not result.success or not result.data:
        log.warning("reader_failed", arxiv_id=paper.arxiv_id)
        return None

    return _parse_analysis(result.data, paper.arxiv_id)


def _read_chunked(agent: Agent, paper: PaperText, topic: str) -> PaperAnalysis | None:
    """Process a long paper in chunks with running summary."""
    chunks = chunk_text(paper.raw_text)
    running_summary = ""

    for i, chunk in enumerate(chunks):
        context = f"Research topic: {topic}\n"
        context += f"Paper (arxiv ID: {paper.arxiv_id}), chunk {i + 1}/{len(chunks)}:\n\n"
        if running_summary:
            context += f"Summary of previous chunks:\n{running_summary}\n\n"
        context += chunk

        result = agent.run(context)
        if result.success and result.data:
            running_summary = result.data.get("core_contribution", running_summary)
            if i == len(chunks) - 1:
                return _parse_analysis(result.data, paper.arxiv_id)

    return None


def _parse_analysis(data: dict, arxiv_id: str) -> PaperAnalysis:
    """Parse agent output into a PaperAnalysis object."""
    algorithms = []
    for algo_data in data.get("algorithms", []):
        spec = AlgorithmSpec(
            name=algo_data.get("name", "unknown"),
            description=algo_data.get("description", ""),
            pseudocode=algo_data.get("pseudocode", ""),
            math_formulation=algo_data.get("math_formulation", ""),
            inputs=algo_data.get("inputs", []),
            outputs=algo_data.get("outputs", []),
            complexity=algo_data.get("complexity", ""),
            dependencies=algo_data.get("dependencies", []),
            test_criteria=algo_data.get("test_criteria", []),
            implementable=algo_data.get("implementable", True),
        )
        algorithms.append(spec)

    analysis = PaperAnalysis(
        arxiv_id=arxiv_id,
        title=data.get("title", ""),
        core_contribution=data.get("core_contribution", ""),
        algorithms=algorithms,
        key_data_structures=data.get("key_data_structures", []),
        paper_dependencies=data.get("paper_dependencies", []),
    )

    log.info(
        "reader_complete",
        arxiv_id=arxiv_id,
        algorithms=len(algorithms),
        implementable=sum(1 for a in algorithms if a.implementable),
    )
    return analysis
