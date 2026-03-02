from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Protocol, Tuple, runtime_checkable

@runtime_checkable
class StepConfig(Protocol):
    enabled: bool
    output_keys: Tuple[str, ...]

@dataclass(frozen=True)
class PipelineConfig:
    force: bool = False
    settings: Dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class PipelineContext:
    src: Path
    force: bool = False
    dry_run: bool = False
    interrupted: bool = False
    outputs: Dict[str, Path] = field(default_factory=dict)
    timings: Dict[str, float] = field(default_factory=dict)
    step_progress: Optional[Callable[[int, int], None]] = None
