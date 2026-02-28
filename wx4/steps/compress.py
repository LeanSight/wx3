"""
Compress step - compresses video using ffmpeg.
"""

import dataclasses
import time
from pathlib import Path

from wx4.compress_video import (
    LufsInfo,
    calculate_video_bitrate,
    compress_video as _compress_video,
    detect_best_encoder,
    measure_audio_lufs,
    probe_video,
)
from wx4.context import INTERMEDIATE_BY_STEP, PipelineContext


def compress_step(ctx: PipelineContext) -> PipelineContext:
    """
    Compress the original source video using compress_video routines.
    If ctx.enhanced exists, uses its audio instead of the video's original audio.
    Raises RuntimeError if src is not a video file or probe fails.
    """
    t0 = time.time()
    src = ctx.src
    out = src.parent / f"{src.stem}{INTERMEDIATE_BY_STEP['compress']}"

    audio_source = ctx.enhanced if ctx.enhanced is not None else src

    try:
        info = probe_video(src)
    except RuntimeError:
        return dataclasses.replace(
            ctx, timings={**ctx.timings, "compress": time.time() - t0}
        )

    if ctx.step_progress:
        ctx.step_progress(0, 100)

    if info.has_audio:
        measured = measure_audio_lufs(audio_source)
        lufs = LufsInfo.from_measured(measured)
    else:
        lufs = LufsInfo.noop()

    encoder = detect_best_encoder(force=None)
    bitrate = calculate_video_bitrate(info, ctx.compress_ratio)
    _compress_video(
        info, lufs, encoder, bitrate, out, progress_callback=ctx.step_progress
    )

    return dataclasses.replace(
        ctx, video_compressed=out, timings={**ctx.timings, "compress": time.time() - t0}
    )
