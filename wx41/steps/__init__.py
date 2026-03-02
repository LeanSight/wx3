import pkgutil
import importlib
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional
from pathlib import Path
from wx41.context import PipelineContext

@dataclass(frozen=True)
class StepInfo:
    name: str
    step_fn: Callable[[PipelineContext, Any], PipelineContext]
    config_class: Optional[type] = None
    output_fn: Optional[Callable[[PipelineContext, Any], Dict[str, Path]]] = None
    optional: bool = False
    description: str = ""

STEP_REGISTRY: Dict[str, StepInfo] = {}

def register_step(
    name: str,
    step_fn: Callable[[PipelineContext, Any], PipelineContext],
    output_fn: Optional[Callable[[PipelineContext, Any], Dict[str, Path]]] = None,
    optional: bool = False,
    description: str = "",
    config_class: Optional[type] = None,
):
    STEP_REGISTRY[name] = StepInfo(
        name=name,
        step_fn=step_fn,
        config_class=config_class,
        output_fn=output_fn,
        optional=optional,
        description=description
    )

_STEPS_LOADED = False

def load_steps():
    """Dynamically discover and load all modules in the steps package."""
    global _STEPS_LOADED
    if _STEPS_LOADED:
        return
    steps_dir = Path(__file__).parent
    for _, module_name, is_pkg in pkgutil.iter_modules([str(steps_dir)]):
        if not is_pkg and module_name != "__init__":
            importlib.import_module(f"wx41.steps.{module_name}")
    _STEPS_LOADED = True

def get_step_info(name: str) -> Optional[StepInfo]:
    load_steps()
    return STEP_REGISTRY.get(name)

def get_all_steps() -> Dict[str, StepInfo]:
    load_steps()
    return STEP_REGISTRY


def predict_output_path(src: Path, step_name: str, key: str) -> Path:
    """Predict the output path for a given step and output key."""
    # Simplify key if it starts with step_name (e.g. transcribe_json -> json)
    # but only if it's not the only part
    suffix = key
    if key.startswith(f"{step_name}_"):
        suffix = key[len(step_name)+1:]
        
    ext = src.suffix
    if "txt" in key:
        ext = ".txt"
    elif "json" in key:
        ext = ".json"
    elif "srt" in key:
        ext = ".srt"
    elif "video" in key or "mp4" in key:
        ext = ".mp4"
        
    return src.parent / f"{src.stem}_{suffix}{ext}"
