"""Test agent: implementation + spec → pytest test module."""

from __future__ import annotations

import json
from pathlib import Path

import structlog

from research_pipeline.agent.base import Agent
from research_pipeline.agent.prompts import TESTER_SYSTEM_PROMPT
from research_pipeline.budget import Budget
from research_pipeline.models import AlgorithmSpec, ImplementationResult, TestResult

log = structlog.get_logger()

MAX_FIX_ROUNDS = 2


def run_tester(
    spec: AlgorithmSpec,
    implementation: ImplementationResult,
    model: str,
    budget: Budget,
    work_dir: Path,
) -> TestResult:
    """Generate and run tests for an algorithm implementation."""
    agent = Agent(
        model=model,
        system_prompt=TESTER_SYSTEM_PROMPT,
        budget=budget,
        work_dir=work_dir,
    )

    module_name = Path(implementation.module_path).stem
    test_path = f"tests/test_{module_name}.py"

    context = (
        f"Write tests for this algorithm implementation.\n\n"
        f"Algorithm specification:\n{json.dumps(_spec_to_dict(spec), indent=2)}\n\n"
        f"Implementation file: {implementation.module_path}\n"
        f"Implementation source:\n```python\n{implementation.source_code}\n```\n\n"
        f"Write tests to: {test_path}\n"
        f"Run tests with: python -m pytest {test_path} -v"
    )

    result = agent.run(context)

    test_file = work_dir / test_path
    if not test_file.exists():
        log.warning("tester_no_tests_written", algorithm=spec.name)
        return TestResult(
            algorithm_name=spec.name,
            test_path=test_path,
            test_output="No test file was created",
            success=False,
        )

    # Parse test results from agent output
    test_result = TestResult(
        algorithm_name=spec.name,
        test_path=test_path,
        success=result.success and result.data.get("success", False) if result.data else False,
        test_output=result.summary,
    )

    if result.data:
        test_result.passed = result.data.get("passed", 0)
        test_result.failed = result.data.get("failed", 0)
        test_result.errors = result.data.get("errors", 0)

    log.info(
        "tester_complete",
        algorithm=spec.name,
        passed=test_result.passed,
        failed=test_result.failed,
        success=test_result.success,
    )
    return test_result


def _spec_to_dict(spec: AlgorithmSpec) -> dict:
    return {
        "name": spec.name,
        "description": spec.description,
        "pseudocode": spec.pseudocode,
        "inputs": spec.inputs,
        "outputs": spec.outputs,
        "test_criteria": spec.test_criteria,
    }
