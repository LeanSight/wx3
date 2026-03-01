"""
wx41 Dynaflow - Walking Skeleton S1
Implementacion con dynaflow library (Amazon States Language).
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from dynaflow import DynaFlow


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


FLOW_DEFINITION = {
    "StartAt": "normalize",
    "States": {
        "normalize": {
            "Type": "Pass",
            "Parameters": {
                "audio_path.$": "$.audio_path",
                "normalized.$": "$.audio_path",
            },
            "ResultPath": "$",
            "Next": "transcribe",
        },
        "transcribe": {
            "Type": "Task",
            "Function": {
                "Handler": "transcribe_handler"
            },
            "Parameters": {
                "audio_path.$": "$.normalized",
                "backend.$": "$.backend",
                "api_key.$": "$.api_key",
            },
            "ResultPath": "$",
            "End": True,
        },
    },
}


def get_functions():
    return {
        "transcribe_handler": transcribe_handler,
    }


def transcribe_handler(audio_path: str, backend: str = "assemblyai", api_key: Optional[str] = None):
    from wx41.transcribe_aai import transcribe_assemblyai
    from wx41.transcribe_whisper import transcribe_whisper

    audio_path = Path(audio_path)

    if backend == "assemblyai":
        txt, jsn = transcribe_assemblyai(
            audio_path,
            api_key=api_key,
            lang=None,
            speakers=None,
            progress_callback=None,
        )
    elif backend == "whisper":
        txt, jsn = transcribe_whisper(
            audio_path,
            api_key=api_key,
            lang=None,
            speakers=None,
            progress_callback=None,
            model="openai/whisper-base",
        )
    else:
        raise RuntimeError(f"Backend {backend} not implemented yet")

    return {
        "transcript_txt": str(txt),
        "transcript_json": str(jsn),
    }


class MediaOrchestrator:
    def __init__(self, config: PipelineConfig, observers: list = None):
        self._config = config
        self._observers = observers or []

    def run(self, src: Path) -> PipelineContext:
        import dataclasses
        ctx = PipelineContext(src=src, force=self._config.force)

        t_cfg = self._config.settings.get("transcribe", TranscribeConfig())

        flow = DynaFlow(FLOW_DEFINITION, functions=get_functions())

        input_data = {
            "audio_path": str(src),
            "backend": t_cfg.backend,
            "api_key": t_cfg.api_key,
        }

        result = flow.run(input_data)

        new_outputs = {
            **ctx.outputs,
            t_cfg.output_keys[0]: Path(result["transcript_txt"]),
            t_cfg.output_keys[1]: Path(result["transcript_json"]),
        }
        return dataclasses.replace(ctx, outputs=new_outputs)
