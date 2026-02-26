"""
Apply ClearVoice speech enhancement.
cv is duck-typed: callable(input_path, online_write) + .write(result, output_path).
"""

from pathlib import Path


def apply_clearvoice(src: Path, dst: Path, cv, progress_callback=None) -> bool:
    """
    Run ClearVoice enhancement on src, writing result to dst.
    cv must be callable and have a .write method.
    progress_callback, if provided, is forwarded to cv() as-is.
    Signature: (done: int, total: int) -> None.
    Exceptions from cv propagate to the caller.
    """
    enhanced = cv(input_path=str(src), online_write=False, progress_callback=progress_callback)
    cv.write(enhanced, output_path=str(dst))
    return True
