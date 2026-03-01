"""
wx41 Pipeco - Walking Skeleton S1
Implementacion alternativa usando pipeco library.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, List
from typing_extensions import Annotated

import pipeco
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
    language: Optional[str] = None
    speakers: Optional[int] = None
    model: str = "openai/whisper-base"

    transcript_txt: Path
    transcript_json: Path

    def run(self):
        from wx41.transcribe_aai import transcribe_assemblyai
        from wx41.transcribe_whisper import transcribe_whisper

        if self.backend == "assemblyai":
            txt, jsn = transcribe_assemblyai(
                self.audio_in,
                api_key=self.api_key,
                lang=self.language,
                speakers=self.speakers,
                progress_callback=None,
            )
        elif self.backend == "whisper":
            txt, jsn = transcribe_whisper(
                self.audio_in,
                api_key=self.api_key,
                lang=self.language,
                speakers=self.speakers,
                progress_callback=None,
                model=self.model,
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
            TranscribeStep.define(
                backend=t_cfg.backend,
                api_key=t_cfg.api_key,
                language=t_cfg.language,
                speakers=t_cfg.speakers,
                model=t_cfg.model,
            ),
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
        ctx = PipelineContext(src=src, force=self._config.force)
        pipeline = build_pipeline(self._config)

        t_cfg = self._config.settings.get("transcribe", TranscribeConfig())

        result = pipeline.run(audio_in=src)

        new_outputs = {
            **ctx.outputs,
            t_cfg.output_keys[0]: result.transcribe.transcript_txt,
            t_cfg.output_keys[1]: result.transcribe.transcript_json,
        }
        return dataclasses.replace(ctx, outputs=new_outputs)


import dataclasses
