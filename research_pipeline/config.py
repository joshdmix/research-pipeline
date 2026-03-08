"""YAML configuration loading."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class ModelConfig:
    orchestrator: str = "claude-opus-4-6"
    agents: str = "claude-sonnet-4-6"


@dataclass
class BudgetConfig:
    max_input_tokens: int = 2_000_000
    max_output_tokens: int = 500_000


@dataclass
class ConcurrencyConfig:
    max_readers: int = 4
    max_testers: int = 4


@dataclass
class DiscoveryConfig:
    max_papers: int = 10
    min_relevance_score: float = 6.0
    date_range_years: int = 5


@dataclass
class Config:
    model: ModelConfig = field(default_factory=ModelConfig)
    budget: BudgetConfig = field(default_factory=BudgetConfig)
    concurrency: ConcurrencyConfig = field(default_factory=ConcurrencyConfig)
    discovery: DiscoveryConfig = field(default_factory=DiscoveryConfig)
    output_base_dir: str = "./output"
    paper_cache: str = "~/.cache/research-pipeline/papers"

    @classmethod
    def load(cls, path: Path | None = None) -> Config:
        if path is None or not path.exists():
            return cls()

        with open(path) as f:
            data = yaml.safe_load(f) or {}

        config = cls()
        if "model" in data:
            config.model = ModelConfig(**data["model"])
        if "budget" in data:
            config.budget = BudgetConfig(**data["budget"])
        if "concurrency" in data:
            config.concurrency = ConcurrencyConfig(**data["concurrency"])
        if "discovery" in data:
            config.discovery = DiscoveryConfig(**data["discovery"])
        if "output" in data:
            config.output_base_dir = data["output"].get("base_dir", config.output_base_dir)
        if "paper_cache" in data:
            config.paper_cache = data["paper_cache"]

        return config

    @property
    def paper_cache_path(self) -> Path:
        return Path(self.paper_cache).expanduser()
