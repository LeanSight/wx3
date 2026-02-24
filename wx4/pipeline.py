"""
Pipeline class and build_steps() factory for wx4.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional

from wx4.context import PipelineContext, Step


@dataclass
class NamedStep:
    """Wraps a step function with a name and optional output path declaration."""

    name: str
    fn: Callable[[PipelineContext], PipelineContext]
    output_fn: Optional[Callable[[PipelineContext], Path]] = None

    def __call__(self, ctx: PipelineContext) -> PipelineContext:
        return self.fn(ctx)

    def output_path(self, ctx: PipelineContext) -> Optional[Path]:
        return self.output_fn(ctx) if self.output_fn else None


class Pipeline:
    """Runs a sequence of steps, threading the context through each one."""

    def __init__(self, steps: List[Step], callbacks: Optional[List] = None) -> None:
        self.steps = steps
        self.callbacks = callbacks or []

    def run(self, ctx: PipelineContext) -> PipelineContext:
        names = [s.name if isinstance(s, NamedStep) else getattr(s, "__name__", repr(s)) for s in self.steps]
        for cb in self.callbacks:
            cb.on_pipeline_start(names)

        for step in self.steps:
            out = step.output_path(ctx) if isinstance(step, NamedStep) else None

            if out is not None and not ctx.force and out.exists():
                for cb in self.callbacks:
                    cb.on_step_skipped(step.name, ctx)
                continue

            name = step.name if isinstance(step, NamedStep) else getattr(step, "__name__", repr(step))
            for cb in self.callbacks:
                cb.on_step_start(name, ctx)
            ctx = step(ctx)
            for cb in self.callbacks:
                cb.on_step_end(name, ctx)

        for cb in self.callbacks:
            cb.on_pipeline_end(ctx)

        return ctx


# Output path lambdas for build_steps()
_ENHANCE_OUT = lambda ctx: ctx.src.parent / f"{ctx.src.stem}_enhanced.m4a"

def _transcript_json(ctx: PipelineContext) -> Path:
    audio = ctx.enhanced if ctx.enhanced is not None else ctx.src
    return audio.parent / f"{audio.stem}_timestamps.json"

def _srt_out(ctx: PipelineContext) -> Path:
    audio = ctx.enhanced if ctx.enhanced is not None else ctx.src
    return audio.parent / f"{audio.stem}_timestamps.srt"

def _video_out(ctx: PipelineContext) -> Path:
    audio = ctx.enhanced if ctx.enhanced is not None else ctx.src
    return audio.parent / f"{audio.stem}_timestamps.mp4"


def build_steps(
    skip_enhance: bool = False,
    videooutput: bool = False,
    force: bool = False,
) -> List[NamedStep]:
    """
    Build the ordered list of pipeline steps based on CLI flags.

    Default order:
      cache_check -> enhance -> cache_save -> transcribe -> srt [-> video]
    With skip_enhance=True:
      transcribe -> srt [-> video]
    """
    from wx4.steps import (
        cache_check_step,
        cache_save_step,
        enhance_step,
        srt_step,
        transcribe_step,
        video_step,
    )

    steps: List[NamedStep] = []

    if not skip_enhance:
        # cache_check and cache_save have no output_fn (their skip logic is internal)
        steps.append(NamedStep("cache_check", cache_check_step))
        steps.append(NamedStep("enhance", enhance_step, _ENHANCE_OUT))
        steps.append(NamedStep("cache_save", cache_save_step))

    steps.append(NamedStep("transcribe", transcribe_step, _transcript_json))
    steps.append(NamedStep("srt", srt_step, _srt_out))

    if videooutput:
        steps.append(NamedStep("video", video_step, _video_out))

    return steps
