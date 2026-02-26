"""
Tests for wx4/transcribe_wx3.py - Whisper + PyAnnote transcription wrapper.
All wx3 modules are mocked - no real models, no audio files, no GPU required.
"""
import json
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FAKE_CHUNKS = [
    {"text": " hola mundo", "timestamp": (0.0, 2.0), "speaker": "SPEAKER_00"},
    {"text": " adios.", "timestamp": (2.5, 4.0), "speaker": "SPEAKER_01"},
]

_FAKE_DIAR_SEGMENTS = [
    {"start": 0.0, "end": 2.0, "speaker": "SPEAKER_00"},
    {"start": 2.5, "end": 4.0, "speaker": "SPEAKER_01"},
]


def _make_transcription_result(chunks):
    result = MagicMock()
    result.chunks = chunks
    result.text = " ".join(c["text"].strip() for c in chunks)
    return result


def _make_diarization_result(segments):
    result = MagicMock()
    result.diarization = MagicMock()
    return result, {"speakers": segments}


# ---------------------------------------------------------------------------
# TestTranscribeWithWhisperOutputFiles
# ---------------------------------------------------------------------------


class TestTranscribeWithWhisperOutputFiles:
    def test_returns_txt_and_json_paths(self, tmp_path):
        from wx4.transcribe_wx3 import transcribe_with_whisper

        audio = tmp_path / "meeting.wav"
        audio.write_bytes(b"fake audio")

        diar_result, diar_dict = _make_diarization_result(_FAKE_DIAR_SEGMENTS)
        trans_result = _make_transcription_result(_FAKE_CHUNKS)

        with patch("wx4.transcribe_wx3.load_media", return_value=MagicMock()), \
             patch("wx4.transcribe_wx3.create_diarization_pipeline", return_value=MagicMock()), \
             patch("wx4.transcribe_wx3.perform_diarization", return_value=(diar_result, MagicMock())), \
             patch("wx4.transcribe_wx3.format_diarization_result", return_value=diar_dict), \
             patch("wx4.transcribe_wx3.create_transcription_pipeline", return_value=MagicMock()), \
             patch("wx4.transcribe_wx3.perform_transcription", return_value=trans_result), \
             patch("wx4.transcribe_wx3.align_diarization_with_transcription", return_value=_FAKE_CHUNKS):
            txt_path, json_path = transcribe_with_whisper(
                audio, hf_token="hf_fake", lang="es", speakers=2
            )

        assert isinstance(txt_path, Path)
        assert isinstance(json_path, Path)
        assert txt_path.suffix == ".txt"
        assert json_path.suffix == ".json"

    def test_json_file_is_created_and_valid(self, tmp_path):
        from wx4.transcribe_wx3 import transcribe_with_whisper

        audio = tmp_path / "meeting.wav"
        audio.write_bytes(b"fake audio")

        diar_result, diar_dict = _make_diarization_result(_FAKE_DIAR_SEGMENTS)
        trans_result = _make_transcription_result(_FAKE_CHUNKS)

        with patch("wx4.transcribe_wx3.load_media", return_value=MagicMock()), \
             patch("wx4.transcribe_wx3.create_diarization_pipeline", return_value=MagicMock()), \
             patch("wx4.transcribe_wx3.perform_diarization", return_value=(diar_result, MagicMock())), \
             patch("wx4.transcribe_wx3.format_diarization_result", return_value=diar_dict), \
             patch("wx4.transcribe_wx3.create_transcription_pipeline", return_value=MagicMock()), \
             patch("wx4.transcribe_wx3.perform_transcription", return_value=trans_result), \
             patch("wx4.transcribe_wx3.align_diarization_with_transcription", return_value=_FAKE_CHUNKS):
            _, json_path = transcribe_with_whisper(audio, hf_token="hf_fake")

        assert json_path.exists()
        words = json.loads(json_path.read_text(encoding="utf-8"))
        assert isinstance(words, list)
        assert len(words) == len(_FAKE_CHUNKS)

    def test_json_words_have_aai_format(self, tmp_path):
        """JSON must have {text, start (ms), end (ms), confidence, speaker}."""
        from wx4.transcribe_wx3 import transcribe_with_whisper

        audio = tmp_path / "meeting.wav"
        audio.write_bytes(b"fake audio")

        diar_result, diar_dict = _make_diarization_result(_FAKE_DIAR_SEGMENTS)
        trans_result = _make_transcription_result(_FAKE_CHUNKS)

        with patch("wx4.transcribe_wx3.load_media", return_value=MagicMock()), \
             patch("wx4.transcribe_wx3.create_diarization_pipeline", return_value=MagicMock()), \
             patch("wx4.transcribe_wx3.perform_diarization", return_value=(diar_result, MagicMock())), \
             patch("wx4.transcribe_wx3.format_diarization_result", return_value=diar_dict), \
             patch("wx4.transcribe_wx3.create_transcription_pipeline", return_value=MagicMock()), \
             patch("wx4.transcribe_wx3.perform_transcription", return_value=trans_result), \
             patch("wx4.transcribe_wx3.align_diarization_with_transcription", return_value=_FAKE_CHUNKS):
            _, json_path = transcribe_with_whisper(audio, hf_token="hf_fake")

        words = json.loads(json_path.read_text(encoding="utf-8"))
        w = words[0]
        assert "text" in w
        assert "start" in w and isinstance(w["start"], int)
        assert "end" in w and isinstance(w["end"], int)
        assert "confidence" in w
        assert "speaker" in w

    def test_txt_file_is_created(self, tmp_path):
        from wx4.transcribe_wx3 import transcribe_with_whisper

        audio = tmp_path / "meeting.wav"
        audio.write_bytes(b"fake audio")

        diar_result, diar_dict = _make_diarization_result(_FAKE_DIAR_SEGMENTS)
        trans_result = _make_transcription_result(_FAKE_CHUNKS)

        with patch("wx4.transcribe_wx3.load_media", return_value=MagicMock()), \
             patch("wx4.transcribe_wx3.create_diarization_pipeline", return_value=MagicMock()), \
             patch("wx4.transcribe_wx3.perform_diarization", return_value=(diar_result, MagicMock())), \
             patch("wx4.transcribe_wx3.format_diarization_result", return_value=diar_dict), \
             patch("wx4.transcribe_wx3.create_transcription_pipeline", return_value=MagicMock()), \
             patch("wx4.transcribe_wx3.perform_transcription", return_value=trans_result), \
             patch("wx4.transcribe_wx3.align_diarization_with_transcription", return_value=_FAKE_CHUNKS):
            txt_path, _ = transcribe_with_whisper(audio, hf_token="hf_fake")

        assert txt_path.exists()
        content = txt_path.read_text(encoding="utf-8")
        assert len(content) > 0

    def test_json_written_atomically(self, tmp_path):
        """Ensures no .json.tmp leftover after completion."""
        from wx4.transcribe_wx3 import transcribe_with_whisper

        audio = tmp_path / "meeting.wav"
        audio.write_bytes(b"fake audio")

        diar_result, diar_dict = _make_diarization_result(_FAKE_DIAR_SEGMENTS)
        trans_result = _make_transcription_result(_FAKE_CHUNKS)

        with patch("wx4.transcribe_wx3.load_media", return_value=MagicMock()), \
             patch("wx4.transcribe_wx3.create_diarization_pipeline", return_value=MagicMock()), \
             patch("wx4.transcribe_wx3.perform_diarization", return_value=(diar_result, MagicMock())), \
             patch("wx4.transcribe_wx3.format_diarization_result", return_value=diar_dict), \
             patch("wx4.transcribe_wx3.create_transcription_pipeline", return_value=MagicMock()), \
             patch("wx4.transcribe_wx3.perform_transcription", return_value=trans_result), \
             patch("wx4.transcribe_wx3.align_diarization_with_transcription", return_value=_FAKE_CHUNKS):
            _, json_path = transcribe_with_whisper(audio, hf_token="hf_fake")

        assert not json_path.with_suffix(".json.tmp").exists()


# ---------------------------------------------------------------------------
# TestTranscribeWithWhisperCallsWx3Pipeline
# ---------------------------------------------------------------------------


class TestTranscribeWithWhisperCallsWx3Pipeline:
    def _run(self, tmp_path, **kwargs):
        from wx4.transcribe_wx3 import transcribe_with_whisper

        audio = tmp_path / "audio.wav"
        audio.write_bytes(b"fake")

        diar_result, diar_dict = _make_diarization_result(_FAKE_DIAR_SEGMENTS)
        trans_result = _make_transcription_result(_FAKE_CHUNKS)

        mocks = {
            "load_media": MagicMock(),
            "create_diarization_pipeline": MagicMock(),
            "perform_diarization": MagicMock(return_value=(diar_result, MagicMock())),
            "format_diarization_result": MagicMock(return_value=diar_dict),
            "create_transcription_pipeline": MagicMock(),
            "perform_transcription": MagicMock(return_value=trans_result),
            "align_diarization_with_transcription": MagicMock(return_value=_FAKE_CHUNKS),
        }

        with patch("wx4.transcribe_wx3.load_media", mocks["load_media"]), \
             patch("wx4.transcribe_wx3.create_diarization_pipeline", mocks["create_diarization_pipeline"]), \
             patch("wx4.transcribe_wx3.perform_diarization", mocks["perform_diarization"]), \
             patch("wx4.transcribe_wx3.format_diarization_result", mocks["format_diarization_result"]), \
             patch("wx4.transcribe_wx3.create_transcription_pipeline", mocks["create_transcription_pipeline"]), \
             patch("wx4.transcribe_wx3.perform_transcription", mocks["perform_transcription"]), \
             patch("wx4.transcribe_wx3.align_diarization_with_transcription", mocks["align_diarization_with_transcription"]):
            transcribe_with_whisper(audio, hf_token="hf_fake", **kwargs)

        return mocks, audio

    def test_load_media_called_with_audio_path(self, tmp_path):
        mocks, audio = self._run(tmp_path)
        mocks["load_media"].assert_called_once_with(audio)

    def test_perform_transcription_called(self, tmp_path):
        mocks, _ = self._run(tmp_path)
        mocks["perform_transcription"].assert_called_once()

    def test_perform_diarization_called_when_hf_token_given(self, tmp_path):
        # _run already uses hf_token="hf_fake"; just verify diarization was called
        mocks, _ = self._run(tmp_path)
        mocks["perform_diarization"].assert_called_once()

    def test_align_called_after_transcription_and_diarization(self, tmp_path):
        mocks, _ = self._run(tmp_path)
        mocks["align_diarization_with_transcription"].assert_called_once()

    def test_language_forwarded_to_transcription(self, tmp_path):
        mocks, _ = self._run(tmp_path, lang="es")
        call_kwargs = mocks["perform_transcription"].call_args[1]
        assert call_kwargs.get("language") == "es" or \
               (mocks["perform_transcription"].call_args[0] and
                "es" in str(mocks["perform_transcription"].call_args))

    def test_output_stem_matches_input_stem(self, tmp_path):
        from wx4.transcribe_wx3 import transcribe_with_whisper

        audio = tmp_path / "my_recording.wav"
        audio.write_bytes(b"fake")

        diar_result, diar_dict = _make_diarization_result(_FAKE_DIAR_SEGMENTS)
        trans_result = _make_transcription_result(_FAKE_CHUNKS)

        with patch("wx4.transcribe_wx3.load_media", return_value=MagicMock()), \
             patch("wx4.transcribe_wx3.create_diarization_pipeline", return_value=MagicMock()), \
             patch("wx4.transcribe_wx3.perform_diarization", return_value=(diar_result, MagicMock())), \
             patch("wx4.transcribe_wx3.format_diarization_result", return_value=diar_dict), \
             patch("wx4.transcribe_wx3.create_transcription_pipeline", return_value=MagicMock()), \
             patch("wx4.transcribe_wx3.perform_transcription", return_value=trans_result), \
             patch("wx4.transcribe_wx3.align_diarization_with_transcription", return_value=_FAKE_CHUNKS):
            txt_path, json_path = transcribe_with_whisper(audio, hf_token="hf_fake")

        assert "my_recording" in json_path.name
        assert "my_recording" in txt_path.name
