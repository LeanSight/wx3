"""
Extract/convert audio to WAV 48kHz mono using ffmpeg.
"""

from pathlib import Path

import ffmpeg
import torch

_GPU: bool = torch.cuda.is_available()


def extract_to_wav(src: Path, dst: Path) -> bool:
    """
    Extract audio to WAV 48kHz mono PCM s16le.
    Uses CUDA hwaccel if _GPU is True; falls back to CPU on failure.
    """

    def _attempt(use_gpu: bool) -> bool:
        try:
            inp = (
                ffmpeg.input(str(src), hwaccel="cuda")
                if use_gpu
                else ffmpeg.input(str(src))
            )
            (
                ffmpeg.output(inp.audio, str(dst), acodec="pcm_s16le", ar=48000, ac=1)
                .run(overwrite_output=True, capture_stdout=True, capture_stderr=True)
            )
            return True
        except ffmpeg.Error:
            return False

    return (_GPU and _attempt(True)) or _attempt(False)
