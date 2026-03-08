"""Main pipeline orchestrator: coordinates all agents through pipeline stages."""

from __future__ import annotations

import json
import re
from pathlib import Path

import anthropic
import structlog

from research_pipeline.agents.discovery import run_discovery
from research_pipeline.agents.implementer import run_implementer
from research_pipeline.agents.reader import run_reader
from research_pipeline.agents.synthesizer import run_synthesizer
from research_pipeline.agents.tester import run_tester
from research_pipeline.budget import Budget
from research_pipeline.config import Config
from research_pipeline.models import (
    AlgorithmSpec,
    ImplementationPlan,
    ImplementationResult,
    PaperAnalysis,
    PaperCandidate,
    PipelineContext,
    PipelineState,
    TestResult,
)
from research_pipeline.paper.extract import extract_paper_text
from research_pipeline.paper.fetch import download_paper

log = structlog.get_logger()


class Orchestrator:
    """Deterministic pipeline orchestrator. Only uses LLM for the PLAN stage."""

    def __init__(self, config: Config):
        self.config = config
        self.budget = Budget(
            max_input_tokens=config.budget.max_input_tokens,
            max_output_tokens=config.budget.max_output_tokens,
        )

    def run_topic(self, topic: str, output_dir: Path) -> PipelineContext:
        """Run the full pipeline for a research topic."""
        topic_slug = _slugify(topic)
        ctx = PipelineContext(
            topic=topic,
            output_dir=output_dir / topic_slug,
            paper_cache_dir=self.config.paper_cache_path,
        )
        ctx.output_dir.mkdir(parents=True, exist_ok=True)

        stages = [
            (PipelineState.DISCOVERING, self._discover),
            (PipelineState.FETCHING, self._fetch),
            (PipelineState.READING, self._read),
            (PipelineState.PLANNING, self._plan),
            (PipelineState.IMPLEMENTING, self._implement),
            (PipelineState.TESTING, self._test),
            (PipelineState.SYNTHESIZING, self._synthesize),
            (PipelineState.VALIDATING, self._validate),
        ]

        for state, stage_fn in stages:
            if self.budget.exhausted:
                log.warning("budget_exhausted_stopping", state=state.value)
                ctx.state = PipelineState.FAILED
                ctx.errors.append(f"Budget exhausted at {state.value}")
                break

            ctx.state = state
            log.info("stage_start", stage=state.value)

            try:
                stage_fn(ctx)
            except Exception as e:
                log.error("stage_failed", stage=state.value, error=str(e))
                ctx.errors.append(f"{state.value}: {e}")
                ctx.state = PipelineState.FAILED
                break
        else:
            ctx.state = PipelineState.COMPLETE

        self._save_state(ctx)
        log.info("pipeline_complete", state=ctx.state.value, budget=self.budget.summary())
        return ctx

    def run_paper(self, arxiv_id: str, output_dir: Path) -> PipelineContext:
        """Run the pipeline for a single paper (MVP mode)."""
        ctx = PipelineContext(
            topic=f"paper-{arxiv_id}",
            output_dir=output_dir,
            paper_cache_dir=self.config.paper_cache_path,
        )
        ctx.output_dir.mkdir(parents=True, exist_ok=True)

        # Skip discovery — go straight to fetch
        ctx.candidates = [
            PaperCandidate(
                arxiv_id=arxiv_id,
                title="",
                abstract="",
                relevance_score=10,
                implementability_score=10,
            )
        ]

        stages = [
            (PipelineState.FETCHING, self._fetch),
            (PipelineState.READING, self._read),
            (PipelineState.PLANNING, self._plan),
            (PipelineState.IMPLEMENTING, self._implement),
            (PipelineState.TESTING, self._test),
            (PipelineState.SYNTHESIZING, self._synthesize),
        ]

        for state, stage_fn in stages:
            if self.budget.exhausted:
                log.warning("budget_exhausted_stopping", state=state.value)
                ctx.errors.append(f"Budget exhausted at {state.value}")
                ctx.state = PipelineState.FAILED
                break

            ctx.state = state
            log.info("stage_start", stage=state.value)

            try:
                stage_fn(ctx)
            except Exception as e:
                log.error("stage_failed", stage=state.value, error=str(e))
                ctx.errors.append(f"{state.value}: {e}")
                ctx.state = PipelineState.FAILED
                break
        else:
            ctx.state = PipelineState.COMPLETE

        self._save_state(ctx)
        log.info("pipeline_complete", state=ctx.state.value, budget=self.budget.summary())
        return ctx

    def _discover(self, ctx: PipelineContext) -> None:
        ctx.candidates = run_discovery(
            topic=ctx.topic,
            model=self.config.model.agents,
            budget=self.budget,
            work_dir=ctx.output_dir,
            max_papers=self.config.discovery.max_papers,
            min_relevance=self.config.discovery.min_relevance_score,
        )
        if not ctx.candidates:
            raise RuntimeError("No papers discovered")

    def _fetch(self, ctx: PipelineContext) -> None:
        for candidate in ctx.candidates:
            try:
                pdf_path = download_paper(candidate.arxiv_id, ctx.paper_cache_dir)
                paper_text = extract_paper_text(pdf_path, candidate.arxiv_id)
                ctx.paper_texts[candidate.arxiv_id] = paper_text
            except Exception as e:
                log.warning("fetch_failed", arxiv_id=candidate.arxiv_id, error=str(e))

        if not ctx.paper_texts:
            raise RuntimeError("Failed to fetch any papers")

    def _read(self, ctx: PipelineContext) -> None:
        for arxiv_id, paper_text in ctx.paper_texts.items():
            try:
                analysis = run_reader(
                    paper=paper_text,
                    topic=ctx.topic,
                    model=self.config.model.agents,
                    budget=self.budget,
                    work_dir=ctx.output_dir,
                )
                if analysis:
                    ctx.analyses.append(analysis)
            except Exception as e:
                log.warning("reader_failed", arxiv_id=arxiv_id, error=str(e))

        if not ctx.analyses:
            raise RuntimeError("Failed to analyze any papers")

    def _plan(self, ctx: PipelineContext) -> None:
        all_algorithms = []
        for analysis in ctx.analyses:
            for algo in analysis.algorithms:
                if algo.implementable:
                    all_algorithms.append(algo)

        if not all_algorithms:
            raise RuntimeError("No implementable algorithms found")

        # Use the orchestrator model for planning decisions
        ctx.plan = self._llm_plan(all_algorithms, ctx.topic)

    def _llm_plan(self, algorithms: list[AlgorithmSpec], topic: str) -> ImplementationPlan:
        """Use Claude to decide implementation order and dependency graph."""
        client = anthropic.Anthropic()

        algo_descriptions = []
        for algo in algorithms:
            algo_descriptions.append(
                f"- {algo.name}: {algo.description} "
                f"(deps: {algo.dependencies or 'none'}, complexity: {algo.complexity or 'unknown'})"
            )

        response = client.messages.create(
            model=self.config.model.orchestrator,
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Topic: {topic}\n\n"
                        f"Algorithms to implement:\n"
                        + "\n".join(algo_descriptions)
                        + "\n\n"
                        "Determine the implementation order (respecting dependencies) and "
                        "create a dependency graph. Return JSON with:\n"
                        '- "order": list of algorithm names in implementation order\n'
                        '- "dependency_graph": dict mapping each algorithm to its dependencies\n'
                        '- "rationale": brief explanation of ordering\n\n'
                        "Return ONLY valid JSON, no markdown."
                    ),
                }
            ],
        )

        self.budget.record_usage(
            response.usage.input_tokens,
            response.usage.output_tokens,
        )

        text = response.content[0].text.strip()
        # Try to extract JSON from the response
        try:
            plan_data = json.loads(text)
        except json.JSONDecodeError:
            json_match = re.search(r"\{.*\}", text, re.DOTALL)
            if json_match:
                plan_data = json.loads(json_match.group())
            else:
                plan_data = {"order": [a.name for a in algorithms], "dependency_graph": {}}

        ordered_names = plan_data.get("order", [a.name for a in algorithms])
        algo_map = {a.name: a for a in algorithms}
        ordered_algorithms = [algo_map[name] for name in ordered_names if name in algo_map]

        # Include any algorithms not in the plan
        for algo in algorithms:
            if algo not in ordered_algorithms:
                ordered_algorithms.append(algo)

        return ImplementationPlan(
            ordered_algorithms=ordered_algorithms,
            dependency_graph=plan_data.get("dependency_graph", {}),
            rationale=plan_data.get("rationale", ""),
        )

    def _implement(self, ctx: PipelineContext) -> None:
        if not ctx.plan:
            raise RuntimeError("No implementation plan")

        topic_slug = _slugify(ctx.topic)

        for spec in ctx.plan.ordered_algorithms:
            if self.budget.exhausted:
                break

            result = run_implementer(
                spec=spec,
                topic_slug=topic_slug,
                model=self.config.model.agents,
                budget=self.budget,
                work_dir=ctx.output_dir,
                existing_implementations=ctx.implementations,
            )
            ctx.implementations.append(result)

        if not any(impl.success for impl in ctx.implementations):
            raise RuntimeError("All implementations failed")

    def _test(self, ctx: PipelineContext) -> None:
        algo_map = {}
        if ctx.plan:
            algo_map = {a.name: a for a in ctx.plan.ordered_algorithms}

        for impl in ctx.implementations:
            if not impl.success:
                continue
            if self.budget.exhausted:
                break

            spec = algo_map.get(impl.algorithm_name)
            if not spec:
                continue

            result = run_tester(
                spec=spec,
                implementation=impl,
                model=self.config.model.agents,
                budget=self.budget,
                work_dir=ctx.output_dir,
            )
            ctx.test_results.append(result)

    def _synthesize(self, ctx: PipelineContext) -> None:
        run_synthesizer(
            topic=ctx.topic,
            analyses=ctx.analyses,
            implementations=ctx.implementations,
            test_results=ctx.test_results,
            model=self.config.model.agents,
            budget=self.budget,
            work_dir=ctx.output_dir,
        )

    def _validate(self, ctx: PipelineContext) -> None:
        """Run final validation checks on the output repository."""
        import subprocess

        # Check all Python files import
        src_dir = ctx.output_dir / "src"
        if src_dir.exists():
            for py_file in src_dir.rglob("*.py"):
                result = subprocess.run(
                    ["python", "-c", f"import importlib.util; spec = importlib.util.spec_from_file_location('m', '{py_file}'); mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode != 0:
                    log.warning("validation_import_fail", file=str(py_file), error=result.stderr)

        # Run pytest if tests exist
        test_dir = ctx.output_dir / "tests"
        if test_dir.exists() and list(test_dir.glob("test_*.py")):
            result = subprocess.run(
                ["python", "-m", "pytest", str(test_dir), "-v", "--tb=short"],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=ctx.output_dir,
            )
            log.info("validation_tests", returncode=result.returncode, output=result.stdout[-500:] if result.stdout else "")

    def _save_state(self, ctx: PipelineContext) -> None:
        """Save pipeline state to JSON for crash recovery."""
        state = {
            "topic": ctx.topic,
            "state": ctx.state.value,
            "candidates": len(ctx.candidates),
            "papers_fetched": len(ctx.paper_texts),
            "analyses": len(ctx.analyses),
            "implementations": [
                {"name": i.algorithm_name, "success": i.success} for i in ctx.implementations
            ],
            "test_results": [
                {"name": t.algorithm_name, "success": t.success} for t in ctx.test_results
            ],
            "errors": ctx.errors,
            "budget": self.budget.summary(),
        }
        state_file = ctx.output_dir / "pipeline_state.json"
        state_file.write_text(json.dumps(state, indent=2))


def _slugify(text: str) -> str:
    """Convert text to a URL/filesystem-friendly slug."""
    slug = text.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug or "research"
