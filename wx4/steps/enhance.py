"""
Enhance step - runs ClearVoice enhancement.
"""

import dataclasses
import time
from pathlib import Path

from wx4.audio_encode import to_aac
from wx4.audio_enhance import apply_clearvoice
from wx4.context import INTERMEDIATE_BY_STEP, PipelineContext
from wx4.model_cache import _get_model

_CV_MODEL = "MossFormer2_SE_48K"


def _load_clearvoice():
    from clearvoice import ClearVoice

    return ClearVoice(task="speech_enhancement", model_names=[_CV_MODEL])


def enhance_step(ctx: PipelineContext) -> PipelineContext:
    """
    Run ClearVoice enhancement on normalized audio (or src if not normalized).
    Returns immediately (with timing) if cache_hit is already True.
    Raises RuntimeError if encode fails.
    """
    t0 = time.time()

    if ctx.cache_hit and ctx.enhanced is not None:
        return dataclasses.replace(
            ctx, timings={**ctx.timings, "enhance": time.time() - t0}
        )

    stem = ctx.src.stem
    d = ctx.src.parent
    tmp_enh = d / f"{stem}._tmp_enh.wav"
    ext = "m4a" if ctx.output_m4a else "wav"
    out = d / f"{stem}{INTERMEDIATE_BY_STEP['enhance']}"

    audio_input = ctx.normalized if ctx.normalized is not None else ctx.src

    cv = _get_model("MossFormer2", _load_clearvoice, None)

    try:
        apply_clearvoice(audio_input, tmp_enh, cv, progress_callback=ctx.step_progress)

        if ctx.output_m4a:
            tmp_out = out.with_suffix(".m4a.tmp")
            if not to_aac(tmp_enh, tmp_out):
                raise RuntimeError(f"to_aac failed for {ctx.src.name}")
            tmp_out.rename(out)
        else:
            tmp_enh.rename(out)
            tmp_enh = None
    finally:
        if tmp_enh is not None and tmp_enh.exists():
            tmp_enh.unlink()

    return dataclasses.replace(
        ctx, enhanced=out, timings={**ctx.timings, "enhance": time.time() - t0}
    )
