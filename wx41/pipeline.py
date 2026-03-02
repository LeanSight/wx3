import dataclasses
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Protocol, runtime_checkable

from wx41.context import PipelineConfig, PipelineContext

@runtime_checkable
class PipelineObserver(Protocol):
    def on_pipeline_start(self, step_names: List[str], ctx: PipelineContext) -> None: ...
    def on_step_start(self, name: str, ctx: PipelineContext) -> None: ...
    def on_step_end(self, name: str, ctx: PipelineContext) -> None: ...
    def on_pipeline_end(self, ctx: PipelineContext) -> None: ...

@dataclass(frozen=True)
class NamedStep:
    name: str
    fn: Callable[[PipelineContext], PipelineContext]
    output_fn: Optional[Callable[[PipelineContext], Dict[str, Path]]] = None

class Pipeline:
    def __init__(self, steps: List[NamedStep], observers: List[PipelineObserver]):
        self._steps = steps
        self._observers = observers

    def _notify(self, action: Callable[[PipelineObserver], None]) -> None:
        for ob in self._observers: action(ob)

    def run(self, ctx: PipelineContext, dry_run: bool = False, resume: bool = False) -> PipelineContext:
        names = [s.name for s in self._steps]
        self._notify(lambda ob: ob.on_pipeline_start(names, ctx))
        if dry_run:
            self._notify(lambda ob: ob.on_pipeline_end(ctx))
            return ctx
        for step in self._steps:
            self._notify(lambda ob: ob.on_step_start(step.name, ctx))
            if resume and step.output_fn:
                outputs_needed = step.output_fn(ctx)
                if outputs_needed and all(p.exists() for p in outputs_needed.values()):
                    new_outputs = {**ctx.outputs, **outputs_needed}
                    ctx = dataclasses.replace(ctx, outputs=new_outputs)
                    self._notify(lambda ob: ob.on_step_end(step.name, ctx))
                    continue
            ctx = step.fn(ctx)
            self._notify(lambda ob: ob.on_step_end(step.name, ctx))
        self._notify(lambda ob: ob.on_pipeline_end(ctx))
        return ctx

def build_audio_pipeline(config: PipelineConfig, observers: List[PipelineObserver]) -> Pipeline:
    from wx41.steps.transcribe import transcribe_step, TranscribeConfig
    t_cfg = config.settings.get('transcribe', TranscribeConfig())

    def transcribe_output_fn(ctx: PipelineContext) -> Dict[str, Path]:
        audio = ctx.outputs.get('enhanced') or ctx.outputs.get('normalized') or ctx.src
        txt_path = audio.parent / f"{audio.stem}_whisper.txt"
        jsn_path = audio.parent / f"{audio.stem}_whisper.json"
        return {t_cfg.output_keys[0]: txt_path, t_cfg.output_keys[1]: jsn_path}

    steps = [NamedStep(
        name='transcribe',
        fn=lambda c: transcribe_step(c, t_cfg),
        output_fn=transcribe_output_fn,
    )]
    return Pipeline(steps, observers)

class MediaOrchestrator:
    def __init__(self, config: PipelineConfig, observers: List[PipelineObserver]):
        self._config = config
        self._observers = observers

    def run(self, src: Path, dry_run: bool = False, resume: bool = False) -> PipelineContext:
        ctx = PipelineContext(src=src, force=self._config.force, dry_run=dry_run)
        pipeline = build_audio_pipeline(self._config, self._observers)
        return pipeline.run(ctx, dry_run=dry_run, resume=resume)
