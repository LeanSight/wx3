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
    from wx41.steps import get_all_steps
    from functools import partial
    
    all_steps = get_all_steps()
    steps = []
    
    # Process settings in the order they were provided
    for step_name, step_config in config.settings.items():
        # 1. Skip if step is explicitly disabled in config
        if not getattr(step_config, 'enabled', True):
            continue
            
        # 2. Find step in registry
        step_info = all_steps.get(step_name)
        if not step_info:
            continue
            
        # 3. Create partials for dependency injection (Brecha #4)
        step_fn = partial(step_info.step_fn, config=step_config)
        
        output_fn = None
        if step_info.output_fn:
            output_fn = partial(step_info.output_fn, config=step_config)
            
        steps.append(NamedStep(
            name=step_name,
            fn=step_fn,
            output_fn=output_fn
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
