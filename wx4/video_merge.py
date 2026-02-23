"""
Merge a video stream with a replacement audio track (stream-copy, no re-encode).
"""

from pathlib import Path

import ffmpeg


def merge_video_audio(video: Path, audio: Path, out: Path) -> bool:
    """
    Replace the audio of video with audio, writing to out.
    Both streams are stream-copied (no re-encoding).
    Returns True on success, False on ffmpeg error.
    """
    try:
        (
            ffmpeg.output(
                ffmpeg.input(str(video)).video,
                ffmpeg.input(str(audio)).audio,
                str(out),
                vcodec="copy",
                acodec="copy",
                movflags="+faststart",
                shortest=None,
            ).run(overwrite_output=True, capture_stdout=True, capture_stderr=True)
        )
        return True
    except ffmpeg.Error:
        return False
