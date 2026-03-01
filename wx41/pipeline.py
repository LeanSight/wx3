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
        for ob in self._observers:
            action(ob)

    def run(self, ctx: PipelineContext) -> PipelineContext:
        names = [s.name for s in self._steps]
        self._notify(lambda ob: ob.on_pipeline_start(names, ctx))
        
        for step in self._steps:
            self._notify(lambda ob: ob.on_step_start(step.name, ctx))
            
            # Ejecución del step
            ctx = step.fn(ctx)
            
            # Registro automático de output si el NamedStep tiene output_fn
            if step.output_fn:
                out_path = step.output_fn(ctx)
                new_outputs = {**ctx.outputs, step.name: out_path}
                ctx = dataclasses.replace(ctx, outputs=new_outputs)
            
            self._notify(lambda ob: ob.on_step_end(step.name, ctx))
            
        self._notify(lambda ob: ob.on_pipeline_end(ctx))
        return ctx
