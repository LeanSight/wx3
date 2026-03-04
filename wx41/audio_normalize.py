import subprocess
from pathlib import Path
from typing import Optional, Callable


def measure_lufs(audio: Path) -> float:
    cmd = [
        "ffmpeg",
        "-i",
        str(audio),
        "-af",
        "loudnorm=I=-23:print_format=json",
        "-f",
        "null",
        "-",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    output = result.stderr
    for line in output.split("\n"):
        if "I:" in line:
            try:
                return float(line.split("I:")[1].strip())
            except (IndexError, ValueError):
                pass
    return -23.0


def normalize_lufs(
    src: Path,
    dst: Path,
    target_lufs: float = -23.0,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> bool:
    if progress_callback:
        progress_callback(0, 2)

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(src),
        "-af",
        f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        str(dst),
    ]

    if progress_callback:
        progress_callback(1, 2)

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg error: {result.stderr}")

    if progress_callback:
        progress_callback(2, 2)

    return True
