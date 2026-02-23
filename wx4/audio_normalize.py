"""
Measure and normalize audio loudness (LUFS) using ffmpeg.
"""

import re
import shutil
from pathlib import Path

import ffmpeg

TARGET_LUFS = -23.0


def measure_lufs(wav: Path) -> float:
    """
    Return integrated loudness in LUFS. Returns -70.0 on silence or error.
    """
    try:
        _, stderr = (
            ffmpeg.input(str(wav))
            .output("-", format="null", af="loudnorm=print_format=json")
            .run(capture_stdout=True, capture_stderr=True)
        )
        m = re.search(rb'"input_i"\s*:\s*"([^"]+)"', stderr)
        if m and m.group(1) != b"-inf":
            val = float(m.group(1))
            if val == val:  # NaN check: NaN != NaN
                return val
    except (ffmpeg.Error, ValueError):
        pass
    return -70.0


def normalize_lufs(src: Path, dst: Path) -> bool:
    """
    Apply gain to bring audio to TARGET_LUFS (-23 LUFS).
    Copies without change if audio is silent (LUFS <= -69).
    Falls back to copy on ffmpeg error.
    Always returns True.
    """
    current = measure_lufs(src)
    if current <= -69.0:
        shutil.copy2(src, dst)
        return True

    gain_db = max(min(TARGET_LUFS - current, 30.0), -30.0)
    try:
        (
            ffmpeg.input(str(src))
            .output(str(dst), af=f"volume={gain_db:.2f}dB")
            .run(overwrite_output=True, capture_stdout=True, capture_stderr=True)
        )
    except ffmpeg.Error:
        shutil.copy2(src, dst)
    return True
