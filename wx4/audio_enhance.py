"""
Apply ClearVoice speech enhancement.
cv is duck-typed: callable(input_path, online_write) + .write(result, output_path).
"""

from pathlib import Path


def apply_clearvoice(src: Path, dst: Path, cv) -> bool:
    """
    Run ClearVoice enhancement on src, writing result to dst.
    cv must be callable and have a .write method.
    Exceptions from cv propagate to the caller.
    """
    enhanced = cv(input_path=str(src), online_write=False)
    cv.write(enhanced, output_path=str(dst))
    return True
