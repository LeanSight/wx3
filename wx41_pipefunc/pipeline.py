"""
wx41 Pipefunc - Walking Skeleton S1
Implementacion alternativa usando pipefunc library.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from pipefunc import pipefunc, Pipeline


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


@pipefunc(output_name="normalized")
def normalize(audio_path: Path) -> Path:
    return audio_path


@pipefunc(output_name=("transcript_txt", "transcript_json"))
def transcribe(
    audio_path: Path,
    backend: str = "assemblyai",
    api_key: Optional[str] = None,
    language: Optional[str] = None,
    speakers: Optional[int] = None,
    model: str = "openai/whisper-base",
) -> Tuple[Path, Path]:
    from wx41.transcribe_aai import transcribe_assemblyai
    from wx41.transcribe_whisper import transcribe_whisper

    if backend == "assemblyai":
        txt, jsn = transcribe_assemblyai(
            audio_path,
            api_key=api_key,
            lang=language,
            speakers=speakers,
            progress_callback=None,
        )
    elif backend == "whisper":
        txt, jsn = transcribe_whisper(
            audio_path,
            api_key=api_key,
            lang=language,
            speakers=speakers,
            progress_callback=None,
            model=model,
        )
    else:
        raise RuntimeError(f"Backend {backend} not implemented yet")

    return txt, jsn


def build_pipeline(config: PipelineConfig) -> Pipeline:
    return Pipeline([normalize, transcribe], profile=False)


class MediaOrchestrator:
    def __init__(self, config: PipelineConfig, observers: list = None):
        self._config = config
        self._observers = observers or []

    def run(self, src: Path) -> PipelineContext:
        ctx = PipelineContext(src=src, force=self._config.force)
        pipeline = build_pipeline(self._config)

        t_cfg = self._config.settings.get("transcribe", TranscribeConfig())

        txt, jsn = pipeline(
            "transcript_json",
            audio_path=src,
            backend=t_cfg.backend,
            api_key=t_cfg.api_key,
            language=t_cfg.language,
            speakers=t_cfg.speakers,
            model=t_cfg.model,
        )

        new_outputs = {
            **ctx.outputs,
            t_cfg.output_keys[0]: txt,
            t_cfg.output_keys[1]: jsn,
        }
        return dataclasses.replace(ctx, outputs=new_outputs)


import dataclasses
