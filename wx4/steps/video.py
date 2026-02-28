"""
Video step - generates black-video MP4 from audio.
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
from wx4.video_black import audio_to_black_video


def video_step(ctx: PipelineContext) -> PipelineContext:
    """
    Generate black-video MP4 from the enhanced (or normalized or src) audio.
    If compress_ratio is set, also compress the output video.
    Raises RuntimeError if audio_to_black_video fails.
    """
    t0 = time.time()
    audio = (
        ctx.enhanced
        if ctx.enhanced is not None
        else (ctx.normalized if ctx.normalized is not None else ctx.src)
    )
    out = audio.parent / f"{audio.stem}{INTERMEDIATE_BY_STEP['video']}"

    if not audio_to_black_video(audio, out):
        raise RuntimeError(f"audio_to_black_video failed for {audio.name}")

    if ctx.compress_ratio is not None:
        _compress_video_from_audio(audio, out, ctx.compress_ratio)

    return dataclasses.replace(
        ctx, video_out=out, timings={**ctx.timings, "video": time.time() - t0}
    )


def _compress_video_from_audio(audio: Path, video: Path, compress_ratio: float) -> None:
    """
    Compress video using the same audio track.
    """
    try:
        info = probe_video(video)
    except RuntimeError as exc:
        raise RuntimeError(
            f"_compress_video_from_audio: {video.name} probe failed: {exc}"
        ) from exc

    if info.has_audio:
        measured = measure_audio_lufs(video)
        lufs = LufsInfo.from_measured(measured)
    else:
        lufs = LufsInfo.noop()

    encoder = detect_best_encoder(force=None)
    bitrate = calculate_video_bitrate(info, compress_ratio)
    compressed = video.parent / f"{video.stem}{INTERMEDIATE_BY_STEP['compress']}"
    _compress_video(info, lufs, encoder, bitrate, compressed)
    compressed.rename(video)
