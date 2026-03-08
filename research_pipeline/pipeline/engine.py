"""Pipeline engine: manages stage execution and transitions."""

from __future__ import annotations

from typing import Callable

import structlog

from research_pipeline.models import PipelineContext, PipelineState, StageResult

log = structlog.get_logger()


class PipelineEngine:
    """Runs pipeline stages in sequence with error handling."""

    def __init__(self):
        self.stages: list[tuple[PipelineState, Callable[[PipelineContext], StageResult]]] = []

    def add_stage(
        self,
        state: PipelineState,
        handler: Callable[[PipelineContext], StageResult],
    ) -> None:
        self.stages.append((state, handler))

    def run(self, ctx: PipelineContext) -> PipelineContext:
        """Execute all stages in order."""
        for state, handler in self.stages:
            ctx.state = state
            log.info("engine_stage_start", stage=state.value)

            try:
                result = handler(ctx)
                if not result.success:
                    log.error("engine_stage_failed", stage=state.value, error=result.error)
                    ctx.errors.append(f"{state.value}: {result.error}")
                    ctx.state = PipelineState.FAILED
                    return ctx
            except Exception as e:
                log.error("engine_stage_exception", stage=state.value, error=str(e))
                ctx.errors.append(f"{state.value}: {e}")
                ctx.state = PipelineState.FAILED
                return ctx

            log.info("engine_stage_complete", stage=state.value)

        ctx.state = PipelineState.COMPLETE
        return ctx
