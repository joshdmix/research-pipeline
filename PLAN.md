# Research-to-Prototype Pipeline — Implementation Plan

## 1. Architecture Overview

Multi-stage pipeline with six distinct agent roles orchestrated by a central coordinator.

```
                         ┌──────────────┐
                         │ Orchestrator │
                         │  (main loop) │
                         └──────┬───────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        │                       │                       │
  ┌─────▼──────┐         ┌─────▼──────┐         ┌─────▼──────┐
  │  Discovery  │         │  Discovery  │         │  Discovery  │
  │   Agent     │         │   Agent     │         │   Agent     │
  └─────┬──────┘         └─────┬──────┘         └─────┬──────┘
        │                       │                       │
        └───────────┬───────────┘                       │
                    ▼                                   ▼
             ┌─────────────┐                    ┌─────────────┐
             │ Reader Agent │                    │ Reader Agent │
             │ (per paper)  │                    │ (per paper)  │
             └──────┬──────┘                    └──────┬──────┘
                    │                                   │
                    └───────────┬───────────────────────┘
                                ▼
                    ┌───────────────────────┐
                    │  Implementation Agent  │
                    │  (per algorithm)       │
                    └───────────┬───────────┘
                                ▼
                    ┌───────────────────────┐
                    │    Test Agent          │
                    │ (per implementation)   │
                    └───────────┬───────────┘
                                ▼
                    ┌───────────────────────┐
                    │  Synthesis Agent       │
                    │ (final writeup + repo) │
                    └───────────────────────┘
```

## 2. Tech Stack

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| Language | Python 3.12+ | ML/research ecosystem, arxiv libraries |
| LLM | Anthropic Claude API (`anthropic` SDK) | Primary reasoning engine |
| Model routing | `claude-sonnet-4-6` for agents, `claude-opus-4-6` for orchestrator decisions | Cost vs quality tradeoff |
| Paper discovery | `arxiv` Python package (official API wrapper) | Rate-limited, free, structured |
| PDF parsing | `pymupdf` (PyMuPDF) | Fast, extracts text + math, handles layouts |
| Math notation | `sympy` for symbolic math validation | Verify extracted formulas |
| Code execution sandbox | `subprocess` in temp venv per prototype | Isolation without Docker overhead for MVP |
| Config | YAML (`pyyaml`) | Simple configuration |
| State persistence | SQLite via `sqlite3` stdlib | Pipeline state, paper metadata, agent results |
| CLI | `click` | Standard Python CLI framework |
| Async | `asyncio` + `anthropic` async client | Parallel agent execution |
| Logging | `structlog` | Structured JSON logs, good for agent tracing |

## 3. Agent Roles and Responsibilities

### 3.1 Orchestrator (deterministic Python logic, NOT an LLM agent)

- Parse user topic input and generate search queries
- Manage pipeline state machine (SQLite)
- Spawn discovery agents in parallel
- Deduplicate and rank discovered papers
- Spawn reader agents (parallel, up to N concurrent)
- Collect extracted algorithms, decide which are implementable
- Spawn implementation agents (sequential per algorithm to avoid conflicts)
- Spawn test agents per implementation
- Spawn synthesis agent for final writeup
- Handle retries (max 2 per agent, then skip with note)
- Track token spend and bail if budget exceeded

### 3.2 Discovery Agent (LLM-assisted)

Input: Research topic string, optional constraints (date range, subfield)
Output: List of `PaperCandidate` objects (arxiv ID, title, abstract, relevance score, tags)

Process:
1. LLM generates 5-8 arxiv search queries from the topic
2. Deterministic code hits arxiv API with each query (max 50 results per query)
3. LLM scores and ranks combined results by relevance (0-10) and implementability (0-10)
4. Returns top 8-12 papers sorted by combined score

### 3.3 Reader Agent (LLM-heavy, one per paper)

Input: arxiv paper ID, PDF content (extracted text), research topic
Output: `PaperAnalysis` object

Extracts:
- **Core contribution** (1-2 sentences)
- **Algorithms** (list of `AlgorithmSpec`): name, pseudocode, math formulation, inputs/outputs, complexity
- **Key data structures**
- **Dependencies** on other algorithms/papers
- **Implementability assessment**: can this be coded as standalone function?
- **Test criteria**: what properties should correct implementation satisfy?

### 3.4 Implementation Agent (LLM-heavy, one per algorithm)

Input: `AlgorithmSpec` from reader, any referenced algorithm implementations already completed
Output: Python module with the implementation

Process:
1. Receives algorithm specification (pseudocode, math, I/O description)
2. Plans implementation: helper functions, data structures, edge cases
3. Writes Python code using tools: `write_file`, `read_file`, `run_command`
4. Runs code to verify it imports and executes without errors
5. Iterates up to 3 times on import/runtime errors

### 3.5 Test Agent (LLM, one per implementation)

Input: `AlgorithmSpec` (with test criteria), implementation source code
Output: pytest test module

Test categories:
1. **Property-based tests** (hypothesis): invariants, mathematical properties
2. **Known-answer tests**: small worked examples from paper
3. **Edge case tests**: empty inputs, single elements, boundaries
4. **Comparison tests** (when applicable): compare against brute-force reference

After writing tests, runs them. If failures: determine if test or implementation is wrong, fix (up to 2 rounds).

### 3.6 Synthesis Agent (LLM, runs once at end)

Input: All paper analyses, implementations, test results
Output: `README.md`, `WRITEUP.md`, `pyproject.toml`

## 4. Pipeline Stages

```
Stage 1: DISCOVER
  Input:  topic (str), config (yaml)
  Output: List[PaperCandidate] → saved to DB

Stage 2: FETCH
  Input:  List[PaperCandidate]
  Output: Downloaded PDFs → extracted text saved to DB
  (Deterministic — no LLM)

Stage 3: READ
  Input:  Paper text per paper
  Output: List[PaperAnalysis] with List[AlgorithmSpec] → DB
  (Parallel — one Reader Agent per paper, up to 4 concurrent)

Stage 4: PLAN
  Input:  All AlgorithmSpecs across all papers
  Output: ImplementationPlan — ordered list, dependency graph, estimated complexity
  (Single Orchestrator LLM call — uses opus for this decision)

Stage 5: IMPLEMENT
  Input:  AlgorithmSpec + dependency implementations
  Output: Python source files in output repo
  (Sequential — respects dependency order from PLAN)

Stage 6: TEST
  Input:  Implementation source + AlgorithmSpec
  Output: Test files + test results
  (Parallel — one Test Agent per implementation, up to 4 concurrent)

Stage 7: SYNTHESIZE
  Input:  Everything above
  Output: README.md, WRITEUP.md, pyproject.toml
  (Single agent)

Stage 8: VALIDATE
  Input:  Complete repo
  Output: Final validation report
  (Deterministic — runs all tests, checks imports, lints)
```

Each stage transition recorded in SQLite. Pipeline resumes from last completed stage on crash.

## 5. Paper Processing

### PDF Ingestion

```python
import pymupdf

def extract_paper_text(pdf_path: str) -> PaperText:
    doc = pymupdf.open(pdf_path)
    sections = []
    for page in doc:
        text = page.get_text("text")
        sections.append(text)
    full_text = "\n\n".join(sections)
    return PaperText(raw_text=full_text, page_count=len(doc), char_count=len(full_text))
```

### Download

```python
import arxiv

def download_paper(arxiv_id: str, cache_dir: Path) -> Path:
    paper = next(arxiv.Client().results(arxiv.Search(id_list=[arxiv_id])))
    pdf_path = cache_dir / f"{arxiv_id.replace('/', '_')}.pdf"
    if not pdf_path.exists():
        paper.download_pdf(dirpath=str(cache_dir), filename=pdf_path.name)
    return pdf_path
```

### Chunking

Papers over 80K chars get chunked (~60K chars with 5K overlap). Reader agent processes sequentially with running summary.

### Algorithm Extraction

Reader agent identifies algorithms by looking for:
- "Algorithm N:" blocks with pseudocode
- Mathematical definitions followed by step-by-step procedures
- Theorems with constructive proofs
- Sections titled "Method", "Approach", "Protocol", "Procedure"

Output forced into JSON schema via tool use (`report_analysis` tool).

## 6. Code Generation Strategy

Implementation agent does NOT do one-shot generation:

1. **Decompose**: Break algorithm into functions. Identify inputs, outputs, intermediate data structures.
2. **Scaffold**: Write module skeleton with type hints, docstrings, and `raise NotImplementedError` stubs.
3. **Implement bottom-up**: Start with leaf functions, work up.
4. **Smoke test each function**: Run quick sanity check after each.
5. **Integration**: Wire together, run full algorithm on small example.

For math: reader agent translates LaTeX to plain English + Python-like pseudocode. Complex math uses `numpy` and `sympy`.

## 7. Verification Layer

### Test Generation Example

```python
from hypothesis import given, strategies as st

@given(st.lists(st.integers()))
def test_sort_preserves_length(xs):
    assert len(my_sort(xs)) == len(xs)

@given(st.lists(st.integers()))
def test_sort_is_ordered(xs):
    result = my_sort(xs)
    assert all(result[i] <= result[i+1] for i in range(len(result)-1))
```

### Correctness Loop

```
Test Agent writes tests
    → runs pytest
    → if pass: done
    → if fail:
        → analyze failure
        → test wrong? → fix test, rerun
        → implementation wrong? → report to orchestrator
            → respawn implementation agent with bug report
            → max 2 fix rounds, then mark "partial"
```

### Final Validation (Stage 8, deterministic)

1. All Python files import successfully
2. pytest runs and reports results
3. ruff lint passes
4. README exists and is non-empty
5. WRITEUP references all implementations
6. pyproject.toml is valid

## 8. Output Format: Deliverable Repo

```
{topic-slug}/
├── pyproject.toml              # Package config, dependencies
├── README.md                   # Quick start, usage examples
├── WRITEUP.md                  # Technical writeup of research area
├── REFERENCES.md               # Full citation list with arxiv links
├── src/
│   └── {topic_slug}/
│       ├── __init__.py         # Package init, re-exports
│       ├── algorithm_a.py      # Each algorithm gets its own module
│       ├── algorithm_b.py
│       ├── utils.py            # Shared helpers
│       └── types.py            # Data structures
├── tests/
│   ├── test_algorithm_a.py
│   ├── test_algorithm_b.py
│   └── conftest.py             # Shared fixtures
├── examples/
│   └── demo.py                 # Runnable demo script
└── papers/
    └── notes/
        ├── paper_2301.12345.md # Per-paper analysis notes
        └── paper_2302.67890.md
```

## 9. Orchestrator Management

### State Machine

```python
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
```

### Failure Handling

| Failure Type | Strategy |
|-------------|----------|
| arxiv API down | Retry 3x with exponential backoff, then fail |
| PDF download fails | Skip paper, continue if >= 3 papers remain |
| Reader agent fails | Retry once, then skip paper |
| Implementation agent fails | Retry with error context, then mark "partial" |
| Test agent fails | Retry once, then ship without tests (noted in writeup) |
| Synthesis agent fails | Retry once, then generate minimal README from templates |
| Token budget exceeded | Stop current stage, synthesize whatever is complete |

### Concurrency Control

```python
MAX_CONCURRENT_READERS = 4
MAX_CONCURRENT_TESTERS = 4
IMPLEMENTATION_SEQUENTIAL = True  # Dependency order

semaphore = asyncio.Semaphore(MAX_CONCURRENT_READERS)

async def read_paper(paper: PaperCandidate):
    async with semaphore:
        return await spawn_reader_agent(paper)
```

### Budget Tracking

```python
@dataclass
class Budget:
    max_input_tokens: int = 2_000_000
    max_output_tokens: int = 500_000
    input_tokens_used: int = 0
    output_tokens_used: int = 0

    @property
    def exhausted(self) -> bool:
        return (self.input_tokens_used >= self.max_input_tokens or
                self.output_tokens_used >= self.max_output_tokens)
```

## 10. Project Directory Structure

```
research-pipeline/
├── pyproject.toml
├── README.md
├── CLAUDE.md
├── research_pipeline/
│   ├── __init__.py
│   ├── cli.py                         # Click CLI entry point
│   ├── config.py                      # YAML config loading
│   ├── models.py                      # All data models
│   ├── db.py                          # SQLite state persistence
│   ├── orchestrator.py                # Main pipeline loop, state machine
│   ├── budget.py                      # Token budget tracking
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── base.py                    # Agent base: tool loop, Anthropic API
│   │   ├── tools.py                   # Tool definitions (write_file, read_file, etc.)
│   │   └── prompts.py                 # System prompts per agent type
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── discovery.py               # Discovery agent: topic → paper candidates
│   │   ├── reader.py                  # Reader agent: paper text → analysis
│   │   ├── implementer.py             # Implementation agent: spec → code
│   │   ├── tester.py                  # Test agent: code + spec → tests
│   │   └── synthesizer.py             # Synthesis agent: everything → writeup
│   ├── paper/
│   │   ├── __init__.py
│   │   ├── fetch.py                   # arxiv API wrapper, PDF download
│   │   ├── extract.py                 # PDF text extraction with pymupdf
│   │   └── chunk.py                   # Text chunking for long papers
│   └── pipeline/
│       ├── __init__.py
│       ├── engine.py                  # Pipeline engine (stage runner)
│       ├── stages.py                  # Stage definitions
│       └── types.py                   # PipelineContext, StageResult
├── tests/
│   ├── test_fetch.py
│   ├── test_extract.py
│   ├── test_models.py
│   ├── test_orchestrator.py
│   └── fixtures/
│       └── sample_paper.pdf
└── config.example.yaml
```

### config.example.yaml

```yaml
model:
  orchestrator: claude-opus-4-6
  agents: claude-sonnet-4-6
budget:
  max_input_tokens: 2000000
  max_output_tokens: 500000
concurrency:
  max_readers: 4
  max_testers: 4
discovery:
  max_papers: 10
  min_relevance_score: 6
  date_range_years: 5
output:
  base_dir: ./output
paper_cache: ~/.cache/research-pipeline/papers
```

## 11. Phase Breakdown

### Phase 1: Foundation (MVP)

Goal: Single paper in, working prototype out. No parallelism.

- Project scaffold: `pyproject.toml`, directory structure, CLI entry point
- Core data models (`models.py`): `PaperCandidate`, `PaperAnalysis`, `AlgorithmSpec`
- Agent base class with Anthropic API tool loop
- Tool definitions: `write_file`, `read_file`, `run_command`, `list_files`
- Paper fetcher: download one paper by arxiv ID, extract text with pymupdf
- Reader agent: extract algorithms from one paper
- Implementation agent: implement one algorithm
- Test agent: write and run tests for one implementation
- CLI: `research-pipeline run --paper 2301.12345 --output ./output`
- No database, just JSON files for state

### Phase 2: Full Pipeline

- Discovery agent with arxiv search API
- Topic-based input (`--topic "zero-knowledge proofs"`)
- SQLite state persistence for crash recovery
- Synthesis agent for writeup generation
- Pipeline engine with stage transitions
- YAML config file
- Budget tracking
- Retry logic per stage

### Phase 3: Parallelism and Polish

- Async agent execution with semaphores
- Parallel reader agents
- Parallel test agents
- Progress reporting (structured log output)
- `--resume` flag to continue from last checkpoint
- `--dry-run` flag to show discovery results without implementing
- Validation stage

### Phase 4: Advanced Features (future)

- Web UI for monitoring
- Cross-paper algorithm dependency resolution
- Benchmark generation (performance tests, not just correctness)
- Multi-language output (Rust, Go implementations)
- Citation graph traversal (follow references to foundational papers)

## Key Design Decisions

1. **Orchestrator is deterministic, not an LLM.** Pure Python with simple rules. Only calls Claude for the PLAN stage (deciding which algorithms to implement).

2. **Agents are stateless functions.** Each call is a fresh Anthropic API conversation. State lives in SQLite and filesystem.

3. **Tool use, not prompt-and-pray.** Agents report structured results via tool calls (`report_analysis({"algorithms": [...]})`) not free-text parsing.

4. **Sequential implementation, parallel reading.** Reading is embarrassingly parallel. Implementation has dependencies.

5. **pymupdf over alternatives.** `pdfplumber` is slower. `marker` is overkill. Academic papers are text-based PDFs.

6. **No Docker for MVP.** Algorithmic code in subprocess with fresh virtualenv. Low risk profile.
