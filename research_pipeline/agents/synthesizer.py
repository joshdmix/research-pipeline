"""Synthesis agent: all results → README, WRITEUP, REFERENCES."""

from __future__ import annotations

import json
from pathlib import Path

import structlog

from research_pipeline.agent.base import Agent
from research_pipeline.agent.prompts import SYNTHESIZER_SYSTEM_PROMPT
from research_pipeline.budget import Budget
from research_pipeline.models import (
    ImplementationResult,
    PaperAnalysis,
    TestResult,
)

log = structlog.get_logger()


def run_synthesizer(
    topic: str,
    analyses: list[PaperAnalysis],
    implementations: list[ImplementationResult],
    test_results: list[TestResult],
    model: str,
    budget: Budget,
    work_dir: Path,
) -> bool:
    """Generate final documentation for the output repository."""
    agent = Agent(
        model=model,
        system_prompt=SYNTHESIZER_SYSTEM_PROMPT,
        budget=budget,
        work_dir=work_dir,
    )

    context = _build_context(topic, analyses, implementations, test_results)
    result = agent.run(context)

    if result.success:
        log.info("synthesis_complete", topic=topic)
    else:
        log.warning("synthesis_failed", topic=topic, error=result.summary)

    return result.success


def _build_context(
    topic: str,
    analyses: list[PaperAnalysis],
    implementations: list[ImplementationResult],
    test_results: list[TestResult],
) -> str:
    sections = [f"Research topic: {topic}\n"]

    sections.append("## Paper Analyses\n")
    for analysis in analyses:
        sections.append(f"### {analysis.title} ({analysis.arxiv_id})")
        sections.append(f"Core contribution: {analysis.core_contribution}")
        sections.append(f"Algorithms: {', '.join(a.name for a in analysis.algorithms)}")
        sections.append("")

    sections.append("## Implementations\n")
    for impl in implementations:
        status = "SUCCESS" if impl.success else "PARTIAL"
        sections.append(f"- [{status}] {impl.algorithm_name} → {impl.module_path}")

    sections.append("\n## Test Results\n")
    for test in test_results:
        status = "PASS" if test.success else "FAIL"
        sections.append(
            f"- [{status}] {test.algorithm_name}: {test.passed} passed, {test.failed} failed"
        )

    sections.append(
        "\n\nGenerate README.md, WRITEUP.md, and REFERENCES.md for this output repository. "
        "Use write_file for each document, then report_result when done."
    )

    return "\n".join(sections)
