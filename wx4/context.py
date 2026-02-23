"""
PipelineContext dataclass and Step type alias for wx4 pipeline.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Optional


@dataclass
class PipelineContext:
    """Context passed through each pipeline step."""

    src: Path

    enhanced: Optional[Path] = None
    transcript_txt: Optional[Path] = None
    transcript_json: Optional[Path] = None
    srt: Optional[Path] = None
    video_out: Optional[Path] = None

    srt_mode: str = "speaker-only"
    output_m4a: bool = True
    skip_enhance: bool = False
    force: bool = False
    language: Optional[str] = None
    speakers: Optional[int] = None
    speaker_names: Dict[str, str] = field(default_factory=dict)
    videooutput: bool = False

    cv: Any = None

    cache_hit: bool = False
    timings: Dict[str, float] = field(default_factory=dict)
    cache: Dict[str, Any] = field(default_factory=dict)


Step = Callable[[PipelineContext], PipelineContext]
