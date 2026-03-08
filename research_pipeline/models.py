"""Core data models for the research pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class PipelineState(Enum):
    INIT = "init"
    DISCOVERING = "discovering"
    FETCHING = "fetching"
    READING = "reading"
    PLANNING = "planning"
    IMPLEMENTING = "implementing"
    TESTING = "testing"
    SYNTHESIZING = "synthesizing"
    VALIDATING = "validating"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class PaperCandidate:
    arxiv_id: str
    title: str
    abstract: str
    relevance_score: float = 0.0
    implementability_score: float = 0.0
    tags: list[str] = field(default_factory=list)
    authors: list[str] = field(default_factory=list)
    published: str = ""

    @property
    def combined_score(self) -> float:
        return self.relevance_score + self.implementability_score


@dataclass
class PaperText:
    raw_text: str
    page_count: int
    char_count: int
    arxiv_id: str = ""


@dataclass
class AlgorithmSpec:
    name: str
    description: str
    pseudocode: str
    math_formulation: str = ""
    inputs: list[dict[str, str]] = field(default_factory=list)
    outputs: list[dict[str, str]] = field(default_factory=list)
    complexity: str = ""
    dependencies: list[str] = field(default_factory=list)
    test_criteria: list[str] = field(default_factory=list)
    implementable: bool = True


@dataclass
class PaperAnalysis:
    arxiv_id: str
    title: str
    core_contribution: str
    algorithms: list[AlgorithmSpec] = field(default_factory=list)
    key_data_structures: list[str] = field(default_factory=list)
    paper_dependencies: list[str] = field(default_factory=list)


@dataclass
class ImplementationResult:
    algorithm_name: str
    module_path: str
    source_code: str
    success: bool
    error_message: str = ""
    iterations: int = 1


@dataclass
class TestResult:
    algorithm_name: str
    test_path: str
    passed: int = 0
    failed: int = 0
    errors: int = 0
    test_output: str = ""
    success: bool = False


@dataclass
class ImplementationPlan:
    ordered_algorithms: list[AlgorithmSpec] = field(default_factory=list)
    dependency_graph: dict[str, list[str]] = field(default_factory=dict)
    rationale: str = ""


@dataclass
class PipelineContext:
    topic: str
    output_dir: Path
    paper_cache_dir: Path
    state: PipelineState = PipelineState.INIT
    candidates: list[PaperCandidate] = field(default_factory=list)
    paper_texts: dict[str, PaperText] = field(default_factory=dict)
    analyses: list[PaperAnalysis] = field(default_factory=list)
    plan: ImplementationPlan | None = None
    implementations: list[ImplementationResult] = field(default_factory=list)
    test_results: list[TestResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass
class StageResult:
    stage: str
    success: bool
    data: Any = None
    error: str = ""
