"""
wx41 Pipeco - Walking Skeleton S1
Implementacion con pipeco library.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from pipeco import Step, Pipeline, Pipe


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


class NormalizeStep(Step):
    audio_in: Path
    normalized: Path

    def run(self):
        self.normalized = self.audio_in


class TranscribeStep(Step):
    audio_in: Path
    backend: str = "assemblyai"
    api_key: Optional[str] = None

    transcript_txt: Path
    transcript_json: Path

    def run(self):
        from wx41.transcribe_aai import transcribe_assemblyai
        from wx41.transcribe_whisper import transcribe_whisper

        if self.backend == "assemblyai":
            txt, jsn = transcribe_assemblyai(
                self.audio_in,
                api_key=self.api_key,
                lang=None,
                speakers=None,
                progress_callback=None,
            )
        elif self.backend == "whisper":
            txt, jsn = transcribe_whisper(
                self.audio_in,
                api_key=self.api_key,
                lang=None,
                speakers=None,
                progress_callback=None,
                model="openai/whisper-base",
            )
        else:
            raise RuntimeError(f"Backend {self.backend} not implemented yet")

        self.transcript_txt = txt
        self.transcript_json = jsn


def build_pipeline(config: PipelineConfig) -> Pipeline:
    t_cfg = config.settings.get("transcribe", TranscribeConfig())

    pipeline = Pipeline(
        steps=[
            NormalizeStep.define(),
            TranscribeStep.define(backend=t_cfg.backend, api_key=t_cfg.api_key),
        ],
        pipes=[
            Pipe(from_step="normalize", from_output="normalized", to_step="transcribe", to_input="audio_in"),
        ],
    )
    return pipeline


class MediaOrchestrator:
    def __init__(self, config: PipelineConfig, observers: list = None):
        self._config = config
        self._observers = observers or []

    def run(self, src: Path) -> PipelineContext:
        import dataclasses
        ctx = PipelineContext(src=src, force=self._config.force)

        t_cfg = self._config.settings.get("transcribe", TranscribeConfig())

        pipeline = build_pipeline(self._config)

        result = pipeline.run(audio_in=src)

        new_outputs = {
            **ctx.outputs,
            t_cfg.output_keys[0]: result.transcribe.transcript_txt,
            t_cfg.output_keys[1]: result.transcribe.transcript_json,
        }
        return dataclasses.replace(ctx, outputs=new_outputs)
