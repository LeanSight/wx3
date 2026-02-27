"""
Measure and normalize audio loudness (LUFS) using ffmpeg.
"""

import re
import shutil
from pathlib import Path
from typing import Callable, Optional

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


def _get_duration_us(path: Path) -> int:
    """Get duration in microseconds for progress calculation."""
    try:
        info = ffmpeg.probe(str(path))
        for stream in info.get("streams", []):
            if "duration" in stream:
                return int(float(stream["duration"]) * 1_000_000)
    except Exception:
        pass
    return 0


def normalize_lufs(
    src: Path,
    dst: Path,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> bool:
    """
    Apply gain to bring audio to TARGET_LUFS (-23 LUFS).
    Copies without change if audio is silent (LUFS <= -69).
    Falls back to copy on ffmpeg error.

    Args:
        src: Source audio file
        dst: Destination audio file
        progress_callback: Optional callback (done, total) for progress updates.
            Called with (0-100, 100) during normalization.
    """
    current = measure_lufs(src)
    if current <= -69.0:
        shutil.copy2(src, dst)
        return True

    gain_db = max(min(TARGET_LUFS - current, 30.0), -30.0)
    total_us = _get_duration_us(src)

    try:
        if progress_callback and total_us > 0:
            process = (
                ffmpeg.input(str(src))
                .output(str(dst), af=f"volume={gain_db:.2f}dB")
                .global_args("-progress", "pipe:1", "-nostats")
                .overwrite_output()
                .run_async(pipe_stdout=True, pipe_stderr=True)
            )
            while True:
                raw = process.stdout.readline()
                if not raw:
                    break
                line = raw.decode("utf-8", errors="replace").strip()
                if line.startswith("out_time_ms="):
                    elapsed_us = int(line.split("=")[1])
                    pct = min(int(elapsed_us / total_us * 100), 100)
                    progress_callback(pct, 100)
                elif line == "progress=end":
                    progress_callback(100, 100)
                    break
            process.wait()
        else:
            (
                ffmpeg.input(str(src))
                .output(str(dst), af=f"volume={gain_db:.2f}dB")
                .run(overwrite_output=True, capture_stdout=True, capture_stderr=True)
            )
    except ffmpeg.Error:
        shutil.copy2(src, dst)
    return True
