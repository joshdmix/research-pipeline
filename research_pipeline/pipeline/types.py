"""Pipeline type definitions."""

# Re-export from models for convenience
from research_pipeline.models import PipelineContext, PipelineState, StageResult

__all__ = ["PipelineContext", "PipelineState", "StageResult"]
