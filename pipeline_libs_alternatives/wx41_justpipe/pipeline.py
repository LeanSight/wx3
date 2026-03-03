"""
wx41 Justpipe - Walking Skeleton S1
Implementacion con justpipe library.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from justpipe import Pipe, EventType


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


@dataclass
class State:
    audio_path: Path = None
    normalized: Path = None
    transcript_txt: Path = None
    transcript_json: Path = None


pipe = Pipe()


@pipe.step(to="normalize")
def start(state: State, audio_path: Path):
    state.audio_path = audio_path


@pipe.step(to="transcribe")
def normalize(state: State):
    state.normalized = state.audio_path


def transcribe(state: State, backend: str = "assemblyai", api_key: Optional[str] = None):
    from wx41.transcribe_aai import transcribe_assemblyai
    from wx41.transcribe_whisper import transcribe_whisper

    if backend == "assemblyai":
        txt, jsn = transcribe_assemblyai(
            state.normalized,
            api_key=api_key,
            lang=None,
            speakers=None,
            progress_callback=None,
        )
    elif backend == "whisper":
        txt, jsn = transcribe_whisper(
            state.normalized,
            api_key=api_key,
            lang=None,
            speakers=None,
            progress_callback=None,
            model="openai/whisper-base",
        )
    else:
        raise RuntimeError(f"Backend {backend} not implemented yet")

    state.transcript_txt = txt
    state.transcript_json = jsn


@pipe.step(to="finish")
def transcribe_wrapper(state: State, backend: str = "assemblyai", api_key: Optional[str] = None):
    transcribe(state, backend, api_key)


@pipe.step()
def finish(state: State):
    pass


class MediaOrchestrator:
    def __init__(self, config: PipelineConfig, observers: list = None):
        self._config = config
        self._observers = observers or []
        self._pipe = pipe

    def run(self, src: Path) -> PipelineContext:
        import dataclasses
        ctx = PipelineContext(src=src, force=self._config.force)

        t_cfg = self._config.settings.get("transcribe", TranscribeConfig())

        state = State()
        state.audio_path = src

        for event in self._pipe.run(state, context={"backend": t_cfg.backend, "api_key": t_cfg.api_key}):
            pass

        new_outputs = {
            **ctx.outputs,
            t_cfg.output_keys[0]: state.transcript_txt,
            t_cfg.output_keys[1]: state.transcript_json,
        }
        return dataclasses.replace(ctx, outputs=new_outputs)
