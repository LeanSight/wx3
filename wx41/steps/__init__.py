from typing import Any, Callable, Dict, Optional
from pathlib import Path
from wx41.context import PipelineContext

STEP_REGISTRY: Dict[str, Callable[[PipelineContext, Any], PipelineContext]] = {}

STEP_OUTPUT_FN_REGISTRY: Dict[str, Callable[[PipelineContext], Dict[str, Path]]] = {}


def register_step(
    name: str,
    step_fn: Callable[[PipelineContext, Any], PipelineContext],
    output_fn: Optional[Callable[[PipelineContext], Dict[str, Path]]] = None,
):
    STEP_REGISTRY[name] = step_fn
    if output_fn:
        STEP_OUTPUT_FN_REGISTRY[name] = output_fn
