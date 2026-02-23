"""
Pipeline class and build_steps() factory for wx4.
"""

from typing import List

from wx4.context import PipelineContext, Step


class Pipeline:
    """Runs a sequence of steps, threading the context through each one."""

    def __init__(self, steps: List[Step]) -> None:
        self.steps = steps

    def run(self, ctx: PipelineContext) -> PipelineContext:
        for step in self.steps:
            ctx = step(ctx)
        return ctx


def build_steps(
    skip_enhance: bool = False,
    videooutput: bool = False,
    force: bool = False,
) -> List[Step]:
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

    steps: List[Step] = []

    if not skip_enhance:
        steps.append(cache_check_step)
        steps.append(enhance_step)
        steps.append(cache_save_step)

    steps.append(transcribe_step)
    steps.append(srt_step)

    if videooutput:
        steps.append(video_step)

    return steps
