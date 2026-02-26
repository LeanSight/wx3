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
from wx4.transcribe_wx3 import transcribe_with_whisper
from wx4.compress_video import (
    LufsInfo,
    calculate_video_bitrate,
    compress_video as _compress_video,
    detect_best_encoder,
    measure_audio_lufs,
    probe_video,
)
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
    Also sets normalized=<path> if the normalized file exists.
    force=True always produces a miss.
    """
    t0 = time.time()

    if ctx.force:
        return dataclasses.replace(
            ctx,
            cache_hit=False,
            timings={**ctx.timings, "cache_check": time.time() - t0},
        )

    cache = load_cache()
    key = file_key(ctx.src)
    cached = cache.get(key)

    if cached:
        enhanced = ctx.src.parent / cached["output"]
        if enhanced.exists():
            normalized = ctx.src.parent / f"{ctx.src.stem}_normalized.m4a"
            return dataclasses.replace(
                ctx,
                enhanced=enhanced,
                normalized=normalized if normalized.exists() else None,
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
# normalize_step
# ---------------------------------------------------------------------------


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
    out = d / f"{stem}_normalized.{ext}"

    if out.exists():
        return dataclasses.replace(
            ctx, normalized=out, timings={**ctx.timings, "normalize": time.time() - t0}
        )

    tmp_raw = d / f"{stem}._tmp_raw.wav"
    tmp_norm = d / f"{stem}._tmp_norm.wav"

    try:
        if not extract_to_wav(ctx.src, tmp_raw):
            raise RuntimeError(f"extract_to_wav failed for {ctx.src.name}")

        normalize_lufs(tmp_raw, tmp_norm)

        if ctx.output_m4a:
            tmp_out = out.with_suffix(".m4a.tmp")
            if not to_aac(tmp_norm, tmp_out):
                raise RuntimeError(f"to_aac failed for {ctx.src.name}")
            tmp_out.rename(out)  # atomic
        else:
            tmp_norm.rename(out)  # already atomic
            tmp_norm = None
    finally:
        for f in [tmp_raw, tmp_norm]:
            if f is not None and f.exists():
                f.unlink()

    return dataclasses.replace(
        ctx, normalized=out, timings={**ctx.timings, "normalize": time.time() - t0}
    )


# ---------------------------------------------------------------------------
# enhance_step
# ---------------------------------------------------------------------------


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
    out = d / f"{stem}_enhanced.{ext}"

    audio_input = ctx.normalized if ctx.normalized is not None else ctx.src

    try:
        apply_clearvoice(
            audio_input, tmp_enh, ctx.cv, progress_callback=ctx.step_progress
        )

        if ctx.output_m4a:
            tmp_out = out.with_suffix(".m4a.tmp")
            if not to_aac(tmp_enh, tmp_out):
                raise RuntimeError(f"to_aac failed for {ctx.src.name}")
            tmp_out.rename(out)  # atomic
        else:
            tmp_enh.rename(out)  # already atomic
            tmp_enh = None
    finally:
        if tmp_enh is not None and tmp_enh.exists():
            tmp_enh.unlink()

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
    Transcribe audio using the backend specified in ctx.transcribe_backend.

    - "assemblyai" (default): calls transcribe_assemblyai (requires ASSEMBLY_AI_KEY)
    - "whisper": calls transcribe_with_whisper (local, requires hf_token for diarization)

    Uses ctx.enhanced if set, otherwise ctx.src.
    Raises RuntimeError for unknown backends.
    """
    t0 = time.time()
    audio = ctx.enhanced if ctx.enhanced is not None else ctx.src

    if ctx.transcribe_backend == "assemblyai":
        txt_path, json_path = transcribe_assemblyai(audio, ctx.language, ctx.speakers)
    elif ctx.transcribe_backend == "whisper":
        txt_path, json_path = transcribe_with_whisper(
            audio,
            lang=ctx.language,
            speakers=ctx.speakers,
            hf_token=ctx.hf_token,
            device=ctx.device,
            whisper_model=ctx.whisper_model,
        )
    else:
        raise RuntimeError(
            f"Unknown transcribe_backend: {ctx.transcribe_backend!r}. "
            "Expected 'assemblyai' or 'whisper'."
        )

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
    out = audio.parent / f"{audio.stem}_timestamps.mp4"

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
    compressed = video.parent / f"{video.stem}_compressed.mp4"
    _compress_video(info, lufs, encoder, bitrate, compressed)
    compressed.rename(video)


# ---------------------------------------------------------------------------
# compress_step
# ---------------------------------------------------------------------------


def compress_step(ctx: PipelineContext) -> PipelineContext:
    """
    Compress the original source video using compress_video routines.
    If ctx.enhanced exists, uses its audio instead of the video's original audio.
    Raises RuntimeError if src is not a video file or probe fails.
    """
    t0 = time.time()
    src = ctx.src
    out = src.parent / f"{src.stem}_compressed.mp4"

    audio_source = ctx.enhanced if ctx.enhanced is not None else src

    try:
        info = probe_video(src)
    except RuntimeError as exc:
        raise RuntimeError(
            f"compress_step: {src.name} is not a video file or probe failed: {exc}"
        ) from exc

    if info.has_audio:
        measured = measure_audio_lufs(audio_source)
        lufs = LufsInfo.from_measured(measured)
    else:
        lufs = LufsInfo.noop()

    encoder = detect_best_encoder(force=None)
    bitrate = calculate_video_bitrate(info, ctx.compress_ratio)
    _compress_video(info, lufs, encoder, bitrate, out)

    return dataclasses.replace(
        ctx, video_compressed=out, timings={**ctx.timings, "compress": time.time() - t0}
    )
