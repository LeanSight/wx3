"""
Pipeline class and build_steps() factory for wx4.
"""

import dataclasses
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional

from wx4.context import PipelineConfig, PipelineContext, Step


@dataclass
class StepDecision:
    """Result of dry_run() - represents what would happen for a single step."""

    name: str
    would_run: bool
    output_path: Optional[Path]
    reason: str  # "exists", "not_exists", "force", "no_output_fn"


@dataclass
class NamedStep:
    """Wraps a step function with a name and optional output path declaration."""

    name: str
    fn: Callable[[PipelineContext], PipelineContext]
    output_fn: Optional[Callable[[PipelineContext], Path]] = None
    ctx_setter: Optional[Callable[[PipelineContext, Path], PipelineContext]] = None

    def __call__(self, ctx: PipelineContext) -> PipelineContext:
        return self.fn(ctx)

    def output_path(self, ctx: PipelineContext) -> Optional[Path]:
        return self.output_fn(ctx) if self.output_fn else None

    def set_ctx(self, ctx: PipelineContext, out: Path) -> PipelineContext:
        return self.ctx_setter(ctx, out) if self.ctx_setter else ctx


class Pipeline:
    """Runs a sequence of steps, threading the context through each one."""

    def __init__(self, steps: List[Step], callbacks: Optional[List] = None) -> None:
        self.steps = steps
        self.callbacks = callbacks or []

    def _make_step_progress(self, name: str) -> Callable[[int, int], None]:
        """Return a (done, total) callable that fans out to all callbacks."""
        callbacks = self.callbacks

        def _progress(done: int, total: int) -> None:
            for cb in callbacks:
                fn = getattr(cb, "on_step_progress", None)
                if fn is not None:
                    fn(name, done, total)

        return _progress

    def run(self, ctx: PipelineContext) -> PipelineContext:
        names = [
            s.name if isinstance(s, NamedStep) else getattr(s, "__name__", repr(s))
            for s in self.steps
        ]
        for cb in self.callbacks:
            cb.on_pipeline_start(names, ctx)

        from wx4.steps import cache_check_step

        cache_check_step_fn = None
        for step in self.steps:
            if hasattr(step, "fn") and step.fn is cache_check_step:
                cache_check_step_fn = step
                break

        if cache_check_step_fn is not None:
            ctx = cache_check_step_fn(ctx)

        try:
            for step in self.steps:
                out = step.output_path(ctx) if isinstance(step, NamedStep) else None

                if out is not None and not ctx.force and out.exists():
                    ctx = step.set_ctx(ctx, out)
                    for cb in self.callbacks:
                        cb.on_step_skipped(step.name, ctx)
                    continue

                name = (
                    step.name
                    if isinstance(step, NamedStep)
                    else getattr(step, "__name__", repr(step))
                )
                # Inject a per-step progress forwarder so steps can report chunk progress
                ctx = dataclasses.replace(
                    ctx, step_progress=self._make_step_progress(name)
                )
                for cb in self.callbacks:
                    cb.on_step_start(name, ctx)
                ctx = step(ctx)
                for cb in self.callbacks:
                    cb.on_step_end(name, ctx)
        finally:
            for cb in self.callbacks:
                cb.on_pipeline_end(ctx)

        return ctx

    def dry_run(self, ctx: PipelineContext) -> List[StepDecision]:
        """
        Simulate pipeline execution without running steps.
        Returns a list of StepDecision for each step.
        """
        decisions: List[StepDecision] = []

        from wx4.steps import cache_check_step

        cache_check_step_fn = None
        for step in self.steps:
            if hasattr(step, "fn") and step.fn is cache_check_step:
                cache_check_step_fn = step
                break

        if cache_check_step_fn is not None:
            ctx = cache_check_step_fn(ctx)

        for step in self.steps:
            name = (
                step.name
                if isinstance(step, NamedStep)
                else getattr(step, "__name__", repr(step))
            )

            out = step.output_path(ctx) if isinstance(step, NamedStep) else None

            if out is None:
                decisions.append(
                    StepDecision(
                        name=name,
                        would_run=True,
                        output_path=None,
                        reason="no_output_fn",
                    )
                )
                continue

            if name == "cache_check":
                decisions.append(
                    StepDecision(
                        name=name,
                        would_run=True,
                        output_path=None,
                        reason="no_output_fn",
                    )
                )
                continue

            would_run = not out.exists() or ctx.force
            reason = (
                "force" if ctx.force else ("exists" if out.exists() else "not_exists")
            )

            decisions.append(
                StepDecision(
                    name=name,
                    would_run=would_run,
                    output_path=out,
                    reason=reason,
                )
            )

        return decisions


# Output path lambdas for build_steps() - usa constantes de context.py
from wx4.context import INTERMEDIATE_BY_STEP


_ENHANCE_OUT = lambda ctx: (
    ctx.src.parent / f"{ctx.src.stem}{INTERMEDIATE_BY_STEP['enhance']}"
)
_NORMALIZE_OUT = lambda ctx: (
    ctx.src.parent / f"{ctx.src.stem}{INTERMEDIATE_BY_STEP['normalize']}"
)


_COMPRESS_OUT = lambda ctx: (
    ctx.src.parent / f"{ctx.src.stem}{INTERMEDIATE_BY_STEP['compress']}"
)


def _transcript_json(ctx: PipelineContext) -> Path:
    audio = ctx.enhanced if ctx.enhanced is not None else ctx.src
    return audio.parent / f"{audio.stem}{INTERMEDIATE_BY_STEP['transcribe']}"


def _srt_out(ctx: PipelineContext) -> Path:
    audio = ctx.enhanced if ctx.enhanced is not None else ctx.src
    return audio.parent / f"{audio.stem}{INTERMEDIATE_BY_STEP['srt']}"


def _video_out(ctx: PipelineContext) -> Path:
    audio = ctx.enhanced if ctx.enhanced is not None else ctx.src
    return audio.parent / f"{audio.stem}{INTERMEDIATE_BY_STEP['video']}"


def build_steps(config: PipelineConfig | None = None) -> List[NamedStep]:
    """
    Build the ordered list of pipeline steps based on composition config.

    Default order:
      cache_check -> normalize -> enhance -> cache_save -> transcribe -> srt [-> video]
    With config.skip_normalize=True:
      cache_check -> enhance -> cache_save -> transcribe -> srt [-> video]
    With config.skip_enhance=True:
      transcribe -> srt [-> video]
    With config.skip_normalize=True AND config.skip_enhance=True:
      transcribe -> srt [-> video]
    """
    if config is None:
        config = PipelineConfig()

    from wx4.steps import (
        cache_check_step,
        cache_save_step,
        compress_step,
        enhance_step,
        normalize_step,
        srt_step,
        transcribe_step,
        video_step,
    )

    steps: List[NamedStep] = []

    import dataclasses as _dc

    if not config.skip_enhance:
        steps.append(NamedStep("cache_check", cache_check_step))
        if not config.skip_normalize:
            steps.append(
                NamedStep(
                    "normalize",
                    normalize_step,
                    _NORMALIZE_OUT,
                    ctx_setter=lambda ctx, p: _dc.replace(ctx, normalized=p),
                )
            )
        steps.append(
            NamedStep(
                "enhance",
                enhance_step,
                _ENHANCE_OUT,
                ctx_setter=lambda ctx, p: _dc.replace(ctx, enhanced=p),
            )
        )
        steps.append(NamedStep("cache_save", cache_save_step))

    steps.append(
        NamedStep(
            "transcribe",
            transcribe_step,
            _transcript_json,
            ctx_setter=lambda ctx, p: _dc.replace(ctx, transcript_json=p),
        )
    )
    steps.append(
        NamedStep(
            "srt", srt_step, _srt_out, ctx_setter=lambda ctx, p: _dc.replace(ctx, srt=p)
        )
    )

    if config.videooutput:
        steps.append(
            NamedStep(
                "video",
                video_step,
                _video_out,
                ctx_setter=lambda ctx, p: _dc.replace(ctx, video_out=p),
            )
        )

    if config.compress_ratio is not None:
        steps.append(
            NamedStep(
                "compress",
                compress_step,
                _COMPRESS_OUT,
                ctx_setter=lambda ctx, p: _dc.replace(ctx, video_compressed=p),
            )
        )

    return steps
