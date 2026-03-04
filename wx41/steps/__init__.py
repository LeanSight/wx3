import pkgutil
import importlib
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Tuple
from pathlib import Path
from wx41.context import PipelineContext


@dataclass(frozen=True)
class ConfigVariant:
    name: str
    config: Any


@dataclass(frozen=True)
class StepInfo:
    name: str
    step_fn: Callable[[PipelineContext, Any], PipelineContext]
    config_class: Optional[type] = None
    output_fn: Optional[Callable[[PipelineContext, Any], Dict[str, Path]]] = None
    optional: bool = False
    description: str = ""
    needs_audio_fixture: bool = False
    input_media_type: str = "audio"
    config_variants: Tuple[ConfigVariant, ...] = ()


STEP_REGISTRY: Dict[str, StepInfo] = {}


def register_step(
    name: str,
    step_fn: Callable[[PipelineContext, Any], PipelineContext],
    output_fn: Optional[Callable[[PipelineContext, Any], Dict[str, Path]]] = None,
    optional: bool = False,
    description: str = "",
    config_class: Optional[type] = None,
    needs_audio_fixture: bool = False,
    input_media_type: str = "audio",
    config_variants: Tuple[ConfigVariant, ...] = (),
):
    STEP_REGISTRY[name] = StepInfo(
        name=name,
        step_fn=step_fn,
        config_class=config_class,
        output_fn=output_fn,
        optional=optional,
        description=description,
        needs_audio_fixture=needs_audio_fixture,
        input_media_type=input_media_type,
        config_variants=config_variants,
    )


def predict_output_path(src: Path, step_name: str, key: str) -> Path:
    """Predict the output path for a given step and output key."""
    suffix = key
    if key.startswith(f"{step_name}_"):
        suffix = key[len(step_name) + 1 :]

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
