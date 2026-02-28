"""
Normalize step - normalizes audio LUFS.
"""

import dataclasses
import time
from pathlib import Path

from wx4.audio_encode import to_aac
from wx4.audio_extract import extract_to_wav
from wx4.audio_normalize import normalize_lufs
from wx4.context import INTERMEDIATE_BY_STEP, PipelineContext


def normalize_step(ctx: PipelineContext) -> PipelineContext:
    """
    Run normalization: extract -> normalize LUFS -> encode.
    Returns immediately (with timing) if normalized file already exists.
    Raises RuntimeError if extract or encode fails.
    """
    t0 = time.time()

    stem = ctx.src.stem
    d = ctx.src.parent
    ext = "m4a" if ctx.output_m4a else "wav"
    out = d / f"{stem}{INTERMEDIATE_BY_STEP['normalize']}"

    if ctx.cache_hit or out.exists():
        return dataclasses.replace(
            ctx,
            normalized=out if out.exists() else ctx.normalized,
            timings={**ctx.timings, "normalize": time.time() - t0},
        )

    tmp_raw = d / f"{stem}._tmp_raw.wav"
    tmp_norm = d / f"{stem}._tmp_norm.wav"

    try:
        if ctx.step_progress:
            ctx.step_progress(0, 3)

        if not extract_to_wav(ctx.src, tmp_raw):
            raise RuntimeError(f"extract_to_wav failed for {ctx.src.name}")

        if ctx.step_progress:
            ctx.step_progress(1, 3)

        normalize_lufs(tmp_raw, tmp_norm, progress_callback=ctx.step_progress)

        if ctx.output_m4a:
            tmp_out = out.with_suffix(".m4a.tmp")
            if not to_aac(tmp_norm, tmp_out):
                raise RuntimeError(f"to_aac failed for {ctx.src.name}")
            tmp_out.rename(out)
        else:
            tmp_norm.rename(out)
            tmp_norm = None

        if ctx.step_progress:
            ctx.step_progress(3, 3)
    finally:
        for f in [tmp_raw, tmp_norm]:
            if f is not None and f.exists():
                f.unlink()

    return dataclasses.replace(
        ctx, normalized=out, timings={**ctx.timings, "normalize": time.time() - t0}
    )
