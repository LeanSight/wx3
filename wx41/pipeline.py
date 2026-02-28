import dataclasses
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Protocol, runtime_checkable

from wx41.context import INTERMEDIATE_BY_STEP, PipelineConfig, PipelineContext
from wx41.steps.transcribe import transcribe_step


@runtime_checkable
class PipelineObserver(Protocol):
    def on_pipeline_start(self, step_names: List[str], ctx: PipelineContext) -> None: ...
    def on_step_start(self, name: str, ctx: PipelineContext) -> None: ...
    def on_step_end(self, name: str, ctx: PipelineContext) -> None: ...
    def on_step_skipped(self, name: str, reason: str, ctx: PipelineContext) -> None: ...
    def on_step_progress(self, name: str, done: int, total: int) -> None: ...
    def on_pipeline_end(self, ctx: PipelineContext) -> None: ...


@dataclass
class StepDecision:
    name: str
    would_run: bool
    output_path: Optional[Path]
    reason: str


@dataclass
class NamedStep:
    name: str
    fn: Callable[[PipelineContext], PipelineContext]
    output_fn: Optional[Callable[[PipelineContext], Path]] = None
    skip_fn: Optional[Callable[[PipelineContext], bool]] = None
    ctx_setter: Optional[Callable[[PipelineContext, Path], PipelineContext]] = None

    def __call__(self, ctx: PipelineContext) -> PipelineContext:
        return self.fn(ctx)

    def output_path(self, ctx: PipelineContext) -> Optional[Path]:
        return self.output_fn(ctx) if self.output_fn else None

    def set_ctx(self, ctx: PipelineContext, out: Path) -> PipelineContext:
        return self.ctx_setter(ctx, out) if self.ctx_setter else ctx


class Pipeline:
    def __init__(self, steps: List[NamedStep], observers: List[PipelineObserver]):
        self._steps = steps
        self._observers = observers

    def _notify(self, action: Callable[[PipelineObserver], None]) -> None:
        for ob in self._observers:
            action(ob)

    def _make_progress(self, step_name: str) -> Callable[[int, int], None]:
        def progress(done: int, total: int) -> None:
            self._notify(lambda ob: ob.on_step_progress(step_name, done, total))
        return progress

    def run(self, ctx: PipelineContext) -> PipelineContext:
        names = [s.name for s in self._steps]
        self._notify(lambda ob: ob.on_pipeline_start(names, ctx))
        try:
            for step in self._steps:
                user_skip = step.skip_fn is not None and step.skip_fn(ctx)
                if user_skip:
                    self._notify(lambda ob: ob.on_step_skipped(step.name, "user_skip", ctx))
                    continue

                out = step.output_path(ctx)
                already_done = out is not None and not ctx.force and out.exists()
                if already_done:
                    if step.ctx_setter:
                        ctx = step.set_ctx(ctx, out)
                    self._notify(lambda ob: ob.on_step_skipped(step.name, "already_done", ctx))
                    continue

                ctx = dataclasses.replace(ctx, step_progress=self._make_progress(step.name))
                self._notify(lambda ob: ob.on_step_start(step.name, ctx))
                ctx = step(ctx)
                self._notify(lambda ob: ob.on_step_end(step.name, ctx))
        finally:
            self._notify(lambda ob: ob.on_pipeline_end(ctx))
        return ctx


def _step(name: str, fn: Callable, ctx_field: str, skip_fn: Optional[Callable] = None) -> NamedStep:
    suffix = INTERMEDIATE_BY_STEP[name]
    return NamedStep(
        name=name,
        fn=fn,
        output_fn=lambda ctx: ctx.src.parent / f"{ctx.src.stem}{suffix}",
        skip_fn=skip_fn,
        ctx_setter=lambda ctx, p: dataclasses.replace(ctx, **{ctx_field: p}),
    )


def _transcribe_ctx_setter(ctx: PipelineContext, json_path: Path) -> PipelineContext:
    txt_path = json_path.parent / json_path.name.replace("_timestamps.json", "_transcript.txt")
    return dataclasses.replace(ctx, transcript_json=json_path, transcript_txt=txt_path)


_TRANSCRIBE = NamedStep(
    name="transcribe",
    fn=transcribe_step,
    output_fn=lambda ctx: ctx.src.parent / f"{ctx.src.stem}{INTERMEDIATE_BY_STEP['transcribe']}",
    skip_fn=None,
    ctx_setter=_transcribe_ctx_setter,
)


def build_audio_pipeline(config: PipelineConfig, observers: List[PipelineObserver]) -> Pipeline:
    return Pipeline([_TRANSCRIBE], observers)


class MediaOrchestrator:
    def __init__(self, config: PipelineConfig, observers: List[PipelineObserver]):
        self._config = config
        self._observers = observers

    def run(self, src: Path) -> PipelineContext:
        ctx = PipelineContext(
            src=src,
            force=self._config.force,
            compress_ratio=self._config.compress_ratio,
            assembly_ai_key=self._config.assembly_ai_key,
            hf_token=self._config.hf_token,
        )
        pipeline = build_audio_pipeline(self._config, self._observers)
        return pipeline.run(ctx)
