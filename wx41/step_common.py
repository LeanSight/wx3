import dataclasses
import functools
import time

def timer(step_name: str):
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(ctx, *args, **kwargs):
            t0 = time.perf_counter()
            result = fn(ctx, *args, **kwargs)
            elapsed = time.perf_counter() - t0
            new_timings = {**result.timings, step_name: elapsed}
            return dataclasses.replace(result, timings=new_timings)
        return wrapper
    return decorator
