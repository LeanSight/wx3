"""
Cache check step - checks if src is already in the enhance cache.
"""

import dataclasses
import time

from wx4.cache_io import file_key, load_cache
from wx4.context import INTERMEDIATE_BY_STEP, PipelineContext


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
            normalized = (
                ctx.src.parent / f"{ctx.src.stem}{INTERMEDIATE_BY_STEP['normalize']}"
            )
            return dataclasses.replace(
                ctx,
                enhanced=enhanced,
                normalized=normalized if normalized.exists() else None,
                cache_hit=True,
                cache=cache,
                timings={**ctx.timings, "cache_check": time.time() - t0},
            )

    enhanced_path = ctx.src.parent / f"{ctx.src.stem}{INTERMEDIATE_BY_STEP['enhance']}"
    if enhanced_path.exists():
        normalized = (
            ctx.src.parent / f"{ctx.src.stem}{INTERMEDIATE_BY_STEP['normalize']}"
        )
        return dataclasses.replace(
            ctx,
            enhanced=enhanced_path,
            normalized=normalized if normalized.exists() else None,
            cache_hit=True,
            cache=cache,
            timings={**ctx.timings, "cache_check": time.time() - t0},
        )

    normalized_path = (
        ctx.src.parent / f"{ctx.src.stem}{INTERMEDIATE_BY_STEP['normalize']}"
    )
    if normalized_path.exists():
        return dataclasses.replace(
            ctx,
            normalized=normalized_path,
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
