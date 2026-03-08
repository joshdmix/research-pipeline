"""Stage definitions for the pipeline engine."""

from research_pipeline.models import PipelineState

# Stage ordering for reference
STAGE_ORDER = [
    PipelineState.DISCOVERING,
    PipelineState.FETCHING,
    PipelineState.READING,
    PipelineState.PLANNING,
    PipelineState.IMPLEMENTING,
    PipelineState.TESTING,
    PipelineState.SYNTHESIZING,
    PipelineState.VALIDATING,
]
