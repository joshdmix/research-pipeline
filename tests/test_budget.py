"""Tests for budget tracking."""

from research_pipeline.budget import Budget


def test_budget_not_exhausted():
    budget = Budget(max_input_tokens=1000, max_output_tokens=500)
    assert not budget.exhausted


def test_budget_exhausted_input():
    budget = Budget(max_input_tokens=100, max_output_tokens=500)
    budget.record_usage(100, 0)
    assert budget.exhausted


def test_budget_exhausted_output():
    budget = Budget(max_input_tokens=1000, max_output_tokens=50)
    budget.record_usage(0, 50)
    assert budget.exhausted


def test_budget_remaining():
    budget = Budget(max_input_tokens=1000, max_output_tokens=500)
    budget.record_usage(300, 100)
    assert budget.input_remaining == 700
    assert budget.output_remaining == 400


def test_budget_summary():
    budget = Budget(max_input_tokens=1000, max_output_tokens=500)
    budget.record_usage(500, 250)
    summary = budget.summary()
    assert "50.0%" in summary["input_pct"]
    assert "50.0%" in summary["output_pct"]
