from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from wx41.steps.transcribe import TranscribeConfig


@dataclass(frozen=True)
class PipelineConfig:
    skip_enhance: bool = False
    skip_normalize: bool = False
    compress_ratio: Optional[float] = None
    force: bool = False

    # Los steps publican sus propios configs
    transcribe: Optional["TranscribeConfig"] = None


@dataclass
class PipelineContext:
    src: Path

    enhanced: Optional[Path] = None
    normalized: Optional[Path] = None
    transcript_txt: Optional[Path] = None
    transcript_json: Optional[Path] = None
    srt: Optional[Path] = None
    video_out: Optional[Path] = None
    video_compressed: Optional[Path] = None

    srt_mode: str = "speaker-only"
    force: bool = False
    language: Optional[str] = None
    speakers: Optional[int] = None
    speaker_names: Dict[str, str] = field(default_factory=dict)
    compress_ratio: Optional[float] = None

    step_progress: Optional[Callable[[int, int], None]] = None

    timings: Dict[str, float] = field(default_factory=dict)


Step = Callable[[PipelineContext], PipelineContext]

INTERMEDIATE_BY_STEP = {
    "normalize": "_normalized.m4a",
    "enhance": "_enhanced.m4a",
    "transcribe": "_timestamps.json",
    "transcript": "_transcript.txt",
    "srt": "_timestamps.srt",
    "video": "_timestamps.mp4",
    "compress": "_compressed.mp4",
    "tmp_raw": "._tmp_raw.wav",
    "tmp_norm": "._tmp_norm.wav",
}

INTERMEDIATE_PATTERNS = tuple(dict.fromkeys(INTERMEDIATE_BY_STEP.values()))
