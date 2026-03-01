import dataclasses
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Protocol, runtime_checkable

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
    output_fn: Optional[Callable[[PipelineContext], Path]] = None

class Pipeline:
    def __init__(self, steps: List[NamedStep], observers: List[PipelineObserver]):
        self._steps = steps
        self._observers = observers

    def _notify(self, action: Callable[[PipelineObserver], None]) -> None:
        for ob in self._observers: action(ob)

    def run(self, ctx: PipelineContext) -> PipelineContext:
        names = [s.name for s in self._steps]
        self._notify(lambda ob: ob.on_pipeline_start(names, ctx))
        for step in self._steps:
            self._notify(lambda ob: ob.on_step_start(step.name, ctx))
            ctx = step.fn(ctx)
            if step.output_fn:
                out_path = step.output_fn(ctx)
                new_outputs = {**ctx.outputs, step.name: out_path}
                ctx = dataclasses.replace(ctx, outputs=new_outputs)
            self._notify(lambda ob: ob.on_step_end(step.name, ctx))
        self._notify(lambda ob: ob.on_pipeline_end(ctx))
        return ctx

def build_audio_pipeline(config: PipelineConfig, observers: List[PipelineObserver]) -> Pipeline:
    from wx41.steps.transcribe import transcribe_step, TranscribeConfig
    t_cfg = config.settings.get('transcribe', TranscribeConfig())
    steps = [NamedStep(name='transcribe', fn=lambda c: transcribe_step(c, t_cfg))]
    return Pipeline(steps, observers)

class MediaOrchestrator:
    def __init__(self, config: PipelineConfig, observers: List[PipelineObserver]):
        self._config = config
        self._observers = observers

    def run(self, src: Path) -> PipelineContext:
        ctx = PipelineContext(src=src, force=self._config.force)
        pipeline = build_audio_pipeline(self._config, self._observers)
        return pipeline.run(ctx)
