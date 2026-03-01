"""
wx41 Dynapipeline - Walking Skeleton S1
Implementacion con dynapipeline library.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from dynapipeline import PipelineFactory, PipeLineType, Stage, StageGroup
from dynapipeline.execution import SequentialExecutionStrategy
from dynapipeline.execution.cycle_strategies import OnceCycleStrategy


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


class NormalizeStage(Stage):
    async def execute(self, data):
        return data


class TranscribeStage(Stage):
    def __init__(self, backend: str = "assemblyai", api_key: Optional[str] = None):
        super().__init__()
        self._backend = backend
        self._api_key = api_key

    async def execute(self, data):
        audio_path = Path(data["audio_path"])
        from wx41.transcribe_aai import transcribe_assemblyai
        from wx41.transcribe_whisper import transcribe_whisper

        if self._backend == "assemblyai":
            txt, jsn = transcribe_assemblyai(
                audio_path,
                api_key=self._api_key,
                lang=None,
                speakers=None,
                progress_callback=None,
            )
        elif self._backend == "whisper":
            txt, jsn = transcribe_whisper(
                audio_path,
                api_key=self._api_key,
                lang=None,
                speakers=None,
                progress_callback=None,
                model="openai/whisper-base",
            )
        else:
            raise RuntimeError(f"Backend {self._backend} not implemented yet")

        return {"transcript_txt": txt, "transcript_json": jsn}


def build_pipeline(config: PipelineConfig):
    t_cfg = config.settings.get("transcribe", TranscribeConfig())

    stage1 = NormalizeStage(name="normalize")
    stage2 = TranscribeStage(backend=t_cfg.backend, api_key=t_cfg.api_key)

    group = StageGroup(
        name="main",
        stages=[stage1, stage2],
        cycle_strategy=OnceCycleStrategy(),
        execution_strategy=SequentialExecutionStrategy(),
    )

    factory = PipelineFactory()
    pipeline = factory.create_pipeline(
        pipeline_type=PipeLineType.SIMPLE,
        name="wx41",
        groups=[group],
    )
    return pipeline


class MediaOrchestrator:
    def __init__(self, config: PipelineConfig, observers: list = None):
        self._config = config
        self._observers = observers or []

    async def run(self, src: Path) -> PipelineContext:
        import dataclasses
        ctx = PipelineContext(src=src, force=self._config.force)

        t_cfg = self._config.settings.get("transcribe", TranscribeConfig())

        pipeline = build_pipeline(self._config)

        result = await pipeline.run({"audio_path": str(src)})

        new_outputs = {
            **ctx.outputs,
            t_cfg.output_keys[0]: result["transcript_txt"],
            t_cfg.output_keys[1]: result["transcript_json"],
        }
        return dataclasses.replace(ctx, outputs=new_outputs)
