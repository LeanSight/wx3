"""
wx4.steps - Pipeline step functions.

Este módulo re-exporta funciones para compatibilidad con tests que hacen patch.
Los parches deben apuntar a:
- wx4.steps.cache_check.load_cache
- wx4.steps.cache_save.save_cache
- wx4.steps.normalize.extract_to_wav
- wx4.steps.normalize.normalize_lufs
- wx4.steps.normalize.to_aac
- wx4.steps.enhance.apply_clearvoice
- wx4.steps.enhance.to_aac
- wx4.steps.enhance._load_clearvoice
- wx4.steps.transcribe.transcribe_assemblyai
- wx4.steps.transcribe.transcribe_with_whisper
- wx4.steps.srt.words_to_srt
- wx4.steps.video.audio_to_black_video
- wx4.steps.video.probe_video
- wx4.steps.video.measure_audio_lufs
- wx4.steps.video.LufsInfo
- wx4.steps.video.detect_best_encoder
- wx4.steps.video.calculate_video_bitrate
- wx4.steps.video._compress_video
"""

from wx4.steps.cache_check import cache_check_step
from wx4.steps.cache_save import cache_save_step
from wx4.steps.compress import compress_step
from wx4.steps.enhance import enhance_step
from wx4.steps.normalize import normalize_step
from wx4.steps.srt import srt_step
from wx4.steps.transcribe import transcribe_step
from wx4.steps.video import video_step

# Re-exports para backwards compatibility con tests
from wx4.cache_io import file_key, load_cache, save_cache
from wx4.audio_encode import to_aac
from wx4.audio_enhance import apply_clearvoice
from wx4.audio_extract import extract_to_wav
from wx4.audio_normalize import normalize_lufs
from wx4.compress_video import (
    LufsInfo,
    calculate_video_bitrate,
    compress_video,
    detect_best_encoder,
    measure_audio_lufs,
    probe_video,
)
from wx4.format_srt import words_to_srt
from wx4.model_cache import _get_model
from wx4.transcribe_aai import transcribe_assemblyai
from wx4.transcribe_wx3 import transcribe_with_whisper
from wx4.video_black import audio_to_black_video

__all__ = [
    "cache_check_step",
    "cache_save_step",
    "compress_step",
    "enhance_step",
    "normalize_step",
    "srt_step",
    "transcribe_step",
    "video_step",
    # Re-exported for backwards compatibility
    "file_key",
    "load_cache",
    "save_cache",
    "to_aac",
    "apply_clearvoice",
    "extract_to_wav",
    "normalize_lufs",
    "LufsInfo",
    "calculate_video_bitrate",
    "compress_video",
    "detect_best_encoder",
    "measure_audio_lufs",
    "probe_video",
    "words_to_srt",
    "_get_model",
    "transcribe_assemblyai",
    "transcribe_with_whisper",
    "audio_to_black_video",
]
