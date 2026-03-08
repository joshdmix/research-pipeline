"""Tests for configuration loading."""

from research_pipeline.config import Config


def test_default_config():
    config = Config()
    assert config.model.orchestrator == "claude-opus-4-6"
    assert config.model.agents == "claude-sonnet-4-6"
    assert config.budget.max_input_tokens == 2_000_000


def test_load_nonexistent_file():
    config = Config.load(None)
    assert config.model.agents == "claude-sonnet-4-6"


def test_paper_cache_path():
    config = Config()
    assert config.paper_cache_path.name == "papers"
