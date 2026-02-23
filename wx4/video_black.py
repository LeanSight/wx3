"""
Generate a black-video MP4 from an audio file using ffmpeg.
GPU NVIDIA (h264_nvenc) if available, CPU fallback (libx264 ultrafast).
"""

from pathlib import Path

import ffmpeg
import torch

_GPU: bool = torch.cuda.is_available()

VIDEO_W = 854
VIDEO_H = 480
VIDEO_FPS = 30


def audio_to_black_video(audio: Path, out: Path) -> bool:
    """
    Combine a black lavfi video source with the given audio into a MP4.
    WAV audio is re-encoded to AAC 192k; other formats are stream-copied.
    Returns True on success, False on ffmpeg error.
    """
    is_wav = Path(audio).suffix.lower() == ".wav"

    black = ffmpeg.input(
        f"color=c=black:s={VIDEO_W}x{VIDEO_H}:r={VIDEO_FPS}", f="lavfi"
    )
    audio_in = ffmpeg.input(str(audio))

    if _GPU:
        video_opts = {"vcodec": "h264_nvenc", "preset": "p1", "gpu": 0}
    else:
        video_opts = {"vcodec": "libx264", "preset": "ultrafast", "crf": 35}

    audio_opts = (
        {"acodec": "aac", "audio_bitrate": "192k"} if is_wav else {"acodec": "copy"}
    )

    try:
        (
            ffmpeg.output(
                black.video,
                audio_in.audio,
                str(out),
                **video_opts,
                **audio_opts,
                movflags="+faststart",
                shortest=None,
            ).run(overwrite_output=True, capture_stdout=True, capture_stderr=True)
        )
        return True
    except ffmpeg.Error:
        return False
