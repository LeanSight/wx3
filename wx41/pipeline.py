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

    def run(self, ctx: PipelineContext, dry_run: bool = False) -> PipelineContext:
        names = [s.name for s in self._steps]
        self._notify(lambda ob: ob.on_pipeline_start(names, ctx))
        if dry_run:
            self._notify(lambda ob: ob.on_pipeline_end(ctx))
            return ctx
        should_resume = not ctx.force
        for step in self._steps:
            self._notify(lambda ob: ob.on_step_start(step.name, ctx))
            if should_resume and step.output_fn:
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
    from wx41.steps import STEP_REGISTRY, STEP_OUTPUT_FN_REGISTRY
    import wx41.steps.transcribe
    
    steps = []
    for step_name, step_config in config.settings.items():
        if step_name in STEP_REGISTRY:
            step_fn = STEP_REGISTRY[step_name]
            output_fn = STEP_OUTPUT_FN_REGISTRY.get(step_name)
            
            def make_step_fn(fn, cfg):
                return lambda ctx: fn(ctx, cfg)
            
            def make_output_fn(fn, cfg):
                if fn is None:
                    return None
                return lambda ctx: fn(ctx, cfg)
            
            steps.append(NamedStep(
                name=step_name,
                fn=make_step_fn(step_fn, step_config),
                output_fn=make_output_fn(output_fn, step_config),
            ))
    return Pipeline(steps, observers)

class MediaOrchestrator:
    def __init__(self, config: PipelineConfig, observers: List[PipelineObserver], state_path: Optional[Path] = None):
        self._config = config
        self._observers = observers
        self._state_path = state_path

    def run(self, src: Path, dry_run: bool = False) -> PipelineContext:
        from wx41.ui.interrupt import InterruptHandler
        ctx = PipelineContext(src=src, force=self._config.force, dry_run=dry_run)
        pipeline = build_audio_pipeline(self._config, self._observers)
        
        handler = None
        if self._state_path:
            handler = InterruptHandler(self._state_path)
            handler.install(ctx)
        
        try:
            return pipeline.run(ctx, dry_run=dry_run)
        except KeyboardInterrupt:
            ctx = dataclasses.replace(ctx, interrupted=True)
            return ctx
        finally:
            if handler:
                handler.uninstall()
