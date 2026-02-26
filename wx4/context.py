"""
PipelineContext dataclass and Step type alias for wx4 pipeline.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple


@dataclass(frozen=True)
class PipelineConfig:
    """Build-time pipeline composition flags. Immutable after construction."""

    skip_enhance: bool = False
    skip_normalize: bool = False
    videooutput: bool = False
    compress_ratio: Optional[float] = None  # None = no compression


@dataclass
class PipelineContext:
    """Context passed through each pipeline step."""

    src: Path

    enhanced: Optional[Path] = None
    normalized: Optional[Path] = None
    transcript_txt: Optional[Path] = None
    transcript_json: Optional[Path] = None
    srt: Optional[Path] = None
    video_out: Optional[Path] = None

    srt_mode: str = "speaker-only"
    output_m4a: bool = True
    force: bool = False
    language: Optional[str] = None
    speakers: Optional[int] = None
    speaker_names: Dict[str, str] = field(default_factory=dict)
    compress_ratio: Optional[float] = None
    video_compressed: Optional[Path] = None

    cv: Any = None
    # Injected by Pipeline.run() before each step; fires all callbacks'
    # on_step_progress(step_name, done, total). Steps read this to report
    # fine-grained progress without depending on Rich directly.
    step_progress: Optional[Callable[[int, int], None]] = None

    # --- Transcription backend selection ---
    # "assemblyai" (default, requires ASSEMBLY_AI_KEY) or "whisper" (local, requires hf_token)
    transcribe_backend: str = "assemblyai"
    # HuggingFace token for Pyannote diarization (only used when transcribe_backend="whisper")
    hf_token: Optional[str] = None
    # Whisper model identifier passed to transformers pipeline
    whisper_model: str = "openai/whisper-large-v3"
    # Compute device: "auto", "cpu", "cuda", or "mps"
    device: str = "auto"

    cache_hit: bool = False
    timings: Dict[str, float] = field(default_factory=dict)
    cache: Dict[str, Any] = field(default_factory=dict)


Step = Callable[[PipelineContext], PipelineContext]
