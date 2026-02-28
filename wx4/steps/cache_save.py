"""
Cache save step - saves enhanced path to cache.
"""

import dataclasses
import time

from wx4.cache_io import file_key, save_cache
from wx4.context import PipelineContext


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
