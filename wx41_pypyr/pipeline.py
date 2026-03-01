"""
wx41 Pypyr - Walking Skeleton S1
Implementacion con pypyr library.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import pypyr.pipeline
import pypyr.steps


@dataclass(frozen=True)
class PipelineConfig:
    force: bool = False
    settings: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PipelineContext:
    src: Path
    force: bool = False
    outputs: Dict[str, Path] = field(default_factory=dict)
    timings: Dict[str, float] = field(default_factory=dict)
    step_progress: Optional[Any] = None


@dataclass(frozen=True)
class TranscribeConfig:
    backend: str = "assemblyai"
    api_key: Optional[str] = None
    language: Optional[str] = None
    speakers: Optional[int] = None
    model: str = "openai/whisper-base"
    output_keys: Tuple[str, str] = ("transcript_txt", "transcript_json")


PIPELINE_YAML = """
name: wx41_pipeline
steps:
  - name: wx41.steps.normalize
    description: Normalize audio
  - name: wx41.steps.transcribe
    description: Transcribe audio
"""


class MediaOrchestrator:
    def __init__(self, config: PipelineConfig, observers: list = None):
        self._config = config
        self._observers = observers or []

    def run(self, src: Path) -> PipelineContext:
        import dataclasses
        ctx = PipelineContext(src=src, force=self._config.force)

        t_cfg = self._config.settings.get("transcribe", TranscribeConfig())

        context = {
            "audio_path": str(src),
            "backend": t_cfg.backend,
            "api_key": t_cfg.api_key,
        }

        pipeline = pypyr.pipeline.Pipeline(
            pipeline_name="wx41",
            pipeline_context_in=context,
            py_file="wx41_pypyr.steps",
        )
        pipeline.run()

        new_outputs = {
            **ctx.outputs,
            t_cfg.output_keys[0]: Path(context.get("transcript_txt", "")),
            t_cfg.output_keys[1]: Path(context.get("transcript_json", "")),
        }
        return dataclasses.replace(ctx, outputs=new_outputs)
