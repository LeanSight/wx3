import dataclasses
import functools
import time


def timer(step_name):
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(ctx):
            t0 = time.perf_counter()
            result = fn(ctx)
            elapsed = time.perf_counter() - t0
            return dataclasses.replace(result, timings={**result.timings, step_name: elapsed})
        return wrapper
    return decorator
