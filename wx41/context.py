from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Optional


@dataclass(frozen=True)
class PipelineConfig:
    force: bool = False
    # Contenedor genérico para configuraciones de steps
    # Cada clave es el nombre del step, el valor es su objeto de config o dict
    settings: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineContext:
    src: Path
    force: bool = False

    # Archivos intermedios (Estado)
    enhanced: Optional[Path] = None
    normalized: Optional[Path] = None
    transcript_txt: Optional[Path] = None
    transcript_json: Optional[Path] = None
    srt: Optional[Path] = None
    video_out: Optional[Path] = None
    video_compressed: Optional[Path] = None

    # Parámetros compartidos de negocio (no infraestructura)
    language: Optional[str] = None
    speakers: Optional[int] = None
    speaker_names: Dict[str, str] = field(default_factory=dict)
    compress_ratio: Optional[float] = None

    step_progress: Optional[Callable[[int, int], None]] = None
    timings: Dict[str, float] = field(default_factory=dict)


INTERMEDIATE_BY_STEP = {
    "normalize": "_normalized.m4a",
    "enhance": "_enhanced.m4a",
    "transcribe": "_timestamps.json",
    "transcript": "_transcript.txt",
    "srt": "_timestamps.srt",
    "video": "_timestamps.mp4",
    "compress": "_compressed.mp4",
}
