"""Tests for core data models."""

from research_pipeline.models import (
    AlgorithmSpec,
    PaperAnalysis,
    PaperCandidate,
    PaperText,
    PipelineState,
)


def test_paper_candidate_combined_score():
    candidate = PaperCandidate(
        arxiv_id="2301.12345",
        title="Test Paper",
        abstract="Test abstract",
        relevance_score=7.0,
        implementability_score=8.0,
    )
    assert candidate.combined_score == 15.0


def test_paper_text_fields():
    text = PaperText(
        raw_text="Hello world",
        page_count=1,
        char_count=11,
        arxiv_id="2301.12345",
    )
    assert text.char_count == 11
    assert text.arxiv_id == "2301.12345"


def test_algorithm_spec_defaults():
    spec = AlgorithmSpec(
        name="test_algo",
        description="A test algorithm",
        pseudocode="step 1: do something",
    )
    assert spec.implementable is True
    assert spec.inputs == []
    assert spec.dependencies == []


def test_paper_analysis():
    algo = AlgorithmSpec(name="algo1", description="desc", pseudocode="code")
    analysis = PaperAnalysis(
        arxiv_id="2301.12345",
        title="Test",
        core_contribution="Does something",
        algorithms=[algo],
    )
    assert len(analysis.algorithms) == 1
    assert analysis.algorithms[0].name == "algo1"


def test_pipeline_states():
    assert PipelineState.INIT.value == "init"
    assert PipelineState.COMPLETE.value == "complete"
    assert PipelineState.FAILED.value == "failed"
