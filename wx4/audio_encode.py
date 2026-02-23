"""
Encode audio to AAC M4A using ffmpeg.
"""

from pathlib import Path

import ffmpeg


def to_aac(src: Path, dst: Path, bitrate: str = "192k") -> bool:
    """
    Compress src to AAC M4A at the given bitrate.
    Returns True on success, False on ffmpeg error.
    """
    try:
        (
            ffmpeg.input(str(src))
            .output(str(dst), acodec="aac", audio_bitrate=bitrate)
            .run(overwrite_output=True, capture_stdout=True, capture_stderr=True)
        )
        return True
    except ffmpeg.Error:
        return False
