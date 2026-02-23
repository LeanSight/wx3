"""
Shared fixtures for wx4 tests.
"""

import wave
from pathlib import Path

import pytest


@pytest.fixture
def tmp_audio_wav(tmp_path) -> Path:
    """WAV 48kHz mono silence, created with stdlib wave (no ffmpeg)."""
    p = tmp_path / "test.wav"
    with wave.open(str(p), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(48000)
        # 0.1 seconds of silence
        wf.writeframes(b"\x00" * 48000 * 2 // 10)
    return p


@pytest.fixture
def sample_words():
    """5 AssemblyAI words across 2 speakers."""
    return [
        {"text": "hello", "start": 0, "end": 500, "speaker": "A"},
        {"text": "world", "start": 500, "end": 1000, "speaker": "A"},
        {"text": "hi", "start": 1000, "end": 1500, "speaker": "B"},
        {"text": "there", "start": 1500, "end": 2000, "speaker": "B"},
        {"text": "everyone", "start": 2000, "end": 2500, "speaker": "A"},
    ]
