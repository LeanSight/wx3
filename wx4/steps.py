"""
Pipeline step functions for wx4.
Each step receives a PipelineContext and returns a (possibly new) PipelineContext.
Module-level imports allow tests to patch wx4.steps.<name>.
"""

import dataclasses
import json
import time
from pathlib import Path

from wx4.audio_encode import to_aac
from wx4.audio_enhance import apply_clearvoice
from wx4.audio_extract import extract_to_wav
from wx4.audio_normalize import normalize_lufs
from wx4.cache_io import file_key, load_cache, save_cache
from wx4.context import PipelineContext
from wx4.format_srt import words_to_srt
from wx4.transcribe_aai import transcribe_assemblyai
from wx4.video_black import audio_to_black_video


# ---------------------------------------------------------------------------
# cache_check_step
# ---------------------------------------------------------------------------


def cache_check_step(ctx: PipelineContext) -> PipelineContext:
    """
    Check if src is already in the enhance cache.
    Sets cache_hit=True and enhanced=<path> on hit.
    force=True always produces a miss.
    """
    t0 = time.time()

    if ctx.force:
        return dataclasses.replace(
            ctx, cache_hit=False, timings={**ctx.timings, "cache_check": time.time() - t0}
        )

    cache = load_cache()
    key = file_key(ctx.src)
    cached = cache.get(key)

    if cached:
        enhanced = ctx.src.parent / cached["output"]
        if enhanced.exists():
            return dataclasses.replace(
                ctx,
                enhanced=enhanced,
                cache_hit=True,
                cache=cache,
                timings={**ctx.timings, "cache_check": time.time() - t0},
            )

    return dataclasses.replace(
        ctx,
        cache_hit=False,
        cache=cache,
        timings={**ctx.timings, "cache_check": time.time() - t0},
    )


# ---------------------------------------------------------------------------
# enhance_step
# ---------------------------------------------------------------------------


def enhance_step(ctx: PipelineContext) -> PipelineContext:
    """
    Run the full enhance pipeline: extract -> normalize -> ClearVoice -> encode.
    Returns immediately (with timing) if cache_hit is already True.
    Raises RuntimeError if extract or encode fails.
    """
    t0 = time.time()

    if ctx.cache_hit and ctx.enhanced is not None:
        return dataclasses.replace(
            ctx, timings={**ctx.timings, "enhance": time.time() - t0}
        )

    stem = ctx.src.stem
    d = ctx.src.parent
    tmp_raw = d / f"{stem}._tmp_raw.wav"
    tmp_norm = d / f"{stem}._tmp_norm.wav"
    tmp_enh = d / f"{stem}._tmp_enh.wav"
    ext = "m4a" if ctx.output_m4a else "wav"
    out = d / f"{stem}_enhanced.{ext}"

    if not extract_to_wav(ctx.src, tmp_raw):
        raise RuntimeError(f"extract_to_wav failed for {ctx.src.name}")

    normalize_lufs(tmp_raw, tmp_norm)
    apply_clearvoice(tmp_norm, tmp_enh, ctx.cv)

    if ctx.output_m4a:
        if not to_aac(tmp_enh, out):
            raise RuntimeError(f"to_aac failed for {ctx.src.name}")
    else:
        if tmp_enh.exists():
            tmp_enh.rename(out)

    return dataclasses.replace(
        ctx, enhanced=out, timings={**ctx.timings, "enhance": time.time() - t0}
    )


# ---------------------------------------------------------------------------
# cache_save_step
# ---------------------------------------------------------------------------


def cache_save_step(ctx: PipelineContext) -> PipelineContext:
    """
    Save enhanced path to cache, unless it was a cache hit or enhanced is None.
    """
    t0 = time.time()

    if ctx.cache_hit or ctx.enhanced is None:
        return dataclasses.replace(
            ctx, timings={**ctx.timings, "cache_save": time.time() - t0}
        )

    cache = dict(ctx.cache)
    cache[file_key(ctx.src)] = {"output": ctx.enhanced.name}
    save_cache(cache)

    return dataclasses.replace(
        ctx, cache=cache, timings={**ctx.timings, "cache_save": time.time() - t0}
    )


# ---------------------------------------------------------------------------
# transcribe_step
# ---------------------------------------------------------------------------


def transcribe_step(ctx: PipelineContext) -> PipelineContext:
    """
    Transcribe audio via AssemblyAI.
    Uses ctx.enhanced if set, otherwise ctx.src.
    """
    t0 = time.time()
    audio = ctx.enhanced if ctx.enhanced is not None else ctx.src
    txt_path, json_path = transcribe_assemblyai(audio, ctx.language, ctx.speakers)

    return dataclasses.replace(
        ctx,
        transcript_txt=txt_path,
        transcript_json=json_path,
        timings={**ctx.timings, "transcribe": time.time() - t0},
    )


# ---------------------------------------------------------------------------
# srt_step
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# video_step
# ---------------------------------------------------------------------------


def video_step(ctx: PipelineContext) -> PipelineContext:
    """
    Generate black-video MP4 from the enhanced (or src) audio.
    Raises RuntimeError if audio_to_black_video fails.
    """
    t0 = time.time()
    audio = ctx.enhanced if ctx.enhanced is not None else ctx.src
    out = audio.parent / f"{audio.stem}_video.mp4"

    if not audio_to_black_video(audio, out):
        raise RuntimeError(f"audio_to_black_video failed for {audio.name}")

    return dataclasses.replace(
        ctx, video_out=out, timings={**ctx.timings, "video": time.time() - t0}
    )
