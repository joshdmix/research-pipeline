"""Implementation agent: algorithm spec → Python module."""

from __future__ import annotations

import json
from pathlib import Path

import structlog

from research_pipeline.agent.base import Agent
from research_pipeline.agent.prompts import IMPLEMENTER_SYSTEM_PROMPT
from research_pipeline.budget import Budget
from research_pipeline.models import AlgorithmSpec, ImplementationResult

log = structlog.get_logger()

MAX_RETRIES = 2


def run_implementer(
    spec: AlgorithmSpec,
    topic_slug: str,
    model: str,
    budget: Budget,
    work_dir: Path,
    existing_implementations: list[ImplementationResult] | None = None,
) -> ImplementationResult:
    """Implement an algorithm from its specification."""
    agent = Agent(
        model=model,
        system_prompt=IMPLEMENTER_SYSTEM_PROMPT,
        budget=budget,
        work_dir=work_dir,
    )

    module_name = _to_module_name(spec.name)
    module_path = f"src/{topic_slug}/{module_name}.py"

    context = _build_context(spec, module_path, existing_implementations)

    for attempt in range(1, MAX_RETRIES + 2):
        result = agent.run(context)

        if result.success and result.data.get("success", True):
            # Read back the implementation
            impl_file = work_dir / module_path
            source_code = impl_file.read_text() if impl_file.exists() else ""

            log.info(
                "implementation_complete",
                algorithm=spec.name,
                module=module_path,
                attempts=attempt,
            )
            return ImplementationResult(
                algorithm_name=spec.name,
                module_path=module_path,
                source_code=source_code,
                success=True,
                iterations=attempt,
            )

        if attempt <= MAX_RETRIES:
            error_msg = result.data.get("summary", result.summary) if result.data else result.summary
            context = (
                f"Previous attempt failed: {error_msg}\n\n"
                f"Please fix the implementation and try again.\n\n"
                f"Original spec:\n{json.dumps(_spec_to_dict(spec), indent=2)}"
            )
            log.info("implementation_retry", algorithm=spec.name, attempt=attempt)

    log.warning("implementation_failed", algorithm=spec.name)
    return ImplementationResult(
        algorithm_name=spec.name,
        module_path=module_path,
        source_code="",
        success=False,
        error_message="Max retries exceeded",
        iterations=MAX_RETRIES + 1,
    )


def _build_context(
    spec: AlgorithmSpec,
    module_path: str,
    existing: list[ImplementationResult] | None,
) -> str:
    context = (
        f"Implement the following algorithm as a Python module.\n\n"
        f"Write the implementation to: {module_path}\n\n"
        f"Algorithm specification:\n{json.dumps(_spec_to_dict(spec), indent=2)}"
    )

    if existing:
        context += "\n\nAlready implemented algorithms (available for import):\n"
        for impl in existing:
            if impl.success:
                context += f"- {impl.algorithm_name}: {impl.module_path}\n"

    return context


def _spec_to_dict(spec: AlgorithmSpec) -> dict:
    return {
        "name": spec.name,
        "description": spec.description,
        "pseudocode": spec.pseudocode,
        "math_formulation": spec.math_formulation,
        "inputs": spec.inputs,
        "outputs": spec.outputs,
        "complexity": spec.complexity,
        "dependencies": spec.dependencies,
        "test_criteria": spec.test_criteria,
    }


def _to_module_name(name: str) -> str:
    """Convert an algorithm name to a valid Python module name."""
    import re

    name = name.lower().strip()
    name = re.sub(r"[^a-z0-9]+", "_", name)
    name = name.strip("_")
    return name or "algorithm"
