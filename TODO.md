# TODO

## Before First Run
- [ ] Set `ANTHROPIC_API_KEY` in shell environment
- [ ] Test with a short paper (~10-15 pages), not a textbook — e.g. `2310.06825`

## Bugs Found During Testing
- [ ] No graceful error when `ANTHROPIC_API_KEY` is missing — agent crashes with auth error instead of a clear message
- [ ] Paper 2301.01686 was 318 pages / 666K chars — chunking works but need to consider page count limits or warnings for book-length PDFs

## Phase 2 (Full Pipeline)
- [ ] Discovery agent with arxiv search API
- [ ] Topic-based input (`--topic "zero-knowledge proofs"`)
- [ ] SQLite state persistence for crash recovery
- [ ] Synthesis agent for writeup generation
- [ ] Pipeline engine with stage transitions
- [ ] YAML config file loading
- [ ] Budget tracking wired through all stages
- [ ] Retry logic per stage

## Phase 3 (Parallelism and Polish)
- [ ] Async agent execution with semaphores
- [ ] Parallel reader agents
- [ ] Parallel test agents
- [ ] Progress reporting (structured log output)
- [ ] `--resume` flag to continue from last checkpoint
- [ ] `--dry-run` flag to show discovery results without implementing
- [ ] Validation stage (lint, import checks)

## Phase 4 (Future)
- [ ] Web UI for monitoring
- [ ] Cross-paper algorithm dependency resolution
- [ ] Benchmark generation
- [ ] Multi-language output (Rust, Go)
- [ ] Citation graph traversal
