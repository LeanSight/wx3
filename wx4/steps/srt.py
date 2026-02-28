"""
SRT step - generates SRT file from transcript JSON.
"""

import dataclasses
import json
import time

from wx4.context import PipelineContext
from wx4.format_srt import words_to_srt


def srt_step(ctx: PipelineContext) -> PipelineContext:
    """
    Generate SRT file from transcript JSON.
    Raises RuntimeError if transcript_json is None.
    """
    t0 = time.time()

    if ctx.transcript_json is None:
        raise RuntimeError("transcript_json is None - run transcribe_step first")

    words = json.loads(ctx.transcript_json.read_text(encoding="utf-8"))
    srt_path = ctx.transcript_json.with_suffix(".srt")
    words_to_srt(
        words=words,
        speaker_names=ctx.speaker_names,
        output_file=str(srt_path),
        mode=ctx.srt_mode,
    )

    return dataclasses.replace(
        ctx, srt=srt_path, timings={**ctx.timings, "srt": time.time() - t0}
    )
