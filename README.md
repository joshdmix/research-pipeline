# research-pipeline

Multi-stage AI pipeline that discovers research papers, extracts algorithms, and generates working Python prototypes.

## Quick Start

```bash
pip install -e ".[dev]"

# Run on a single paper
research-pipeline run --paper 2301.12345 --output ./output

# Run on a topic
research-pipeline run --topic "zero-knowledge proofs" --output ./output

# Check status
research-pipeline status --output ./output
```

## How It Works

1. **Discover** — LLM generates arxiv search queries, scores papers by relevance and implementability
2. **Fetch** — Downloads PDFs from arxiv, extracts text with PyMuPDF
3. **Read** — LLM agents analyze papers, extract algorithm specifications
4. **Plan** — Orchestrator determines implementation order from dependency graph
5. **Implement** — LLM agents write Python implementations from specs
6. **Test** — LLM agents generate and run property-based and unit tests
7. **Synthesize** — LLM agent generates README, technical writeup, and references
8. **Validate** — Deterministic checks: imports, tests, linting

## Configuration

Copy `config.example.yaml` and customize:

```bash
cp config.example.yaml config.yaml
research-pipeline run --topic "graph algorithms" --config config.yaml
```

## Requirements

- Python 3.12+
- `ANTHROPIC_API_KEY` environment variable set
