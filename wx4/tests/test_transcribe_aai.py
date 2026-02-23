"""
Tests for wx4/transcribe_aai.py - transcribe_assemblyai().
Mock: wx4.transcribe_aai.aai (the assemblyai module).
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def _make_aai_mock(status="completed", error=None):
    """Return a mock assemblyai module with a working Transcriber."""
    mock_aai = MagicMock()

    # Transcript status
    mock_aai.TranscriptStatus.error = "error"

    # Words
    word = MagicMock()
    word.text = "hello"
    word.start = 0
    word.end = 500
    word.confidence = 0.99
    word.speaker = "A"

    # Utterance
    utt = MagicMock()
    utt.start = 0
    utt.text = "hello"
    utt.speaker = "A"

    transcript = MagicMock()
    transcript.status = status
    transcript.error = error
    transcript.words = [word]
    transcript.utterances = [utt]

    mock_aai.Transcriber.return_value.transcribe.return_value = transcript
    mock_aai.SpeechModel.best = "best"

    return mock_aai


class TestTranscribeAssemblyai:
    def test_raises_when_api_key_env_missing(self, tmp_path, monkeypatch):
        monkeypatch.delenv("ASSEMBLY_AI_KEY", raising=False)
        with patch("wx4.transcribe_aai.aai", MagicMock()):
            from wx4.transcribe_aai import transcribe_assemblyai

            with pytest.raises(RuntimeError, match="ASSEMBLY_AI_KEY"):
                transcribe_assemblyai(tmp_path / "audio.wav")

    def test_sets_api_key_from_env(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ASSEMBLY_AI_KEY", "test-key-123")
        mock_aai = _make_aai_mock()
        with patch("wx4.transcribe_aai.aai", mock_aai):
            from wx4.transcribe_aai import transcribe_assemblyai

            transcribe_assemblyai(tmp_path / "audio.wav")
        assert mock_aai.settings.api_key == "test-key-123"

    def test_config_has_speaker_labels_true(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ASSEMBLY_AI_KEY", "key")
        mock_aai = _make_aai_mock()
        with patch("wx4.transcribe_aai.aai", mock_aai):
            from wx4.transcribe_aai import transcribe_assemblyai

            transcribe_assemblyai(tmp_path / "audio.wav")
        kw = mock_aai.TranscriptionConfig.call_args.kwargs
        assert kw["speaker_labels"] is True

    def test_config_language_code_passed(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ASSEMBLY_AI_KEY", "key")
        mock_aai = _make_aai_mock()
        with patch("wx4.transcribe_aai.aai", mock_aai):
            from wx4.transcribe_aai import transcribe_assemblyai

            transcribe_assemblyai(tmp_path / "audio.wav", lang="es")
        kw = mock_aai.TranscriptionConfig.call_args.kwargs
        assert kw["language_code"] == "es"

    def test_config_language_detection_when_lang_none(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ASSEMBLY_AI_KEY", "key")
        mock_aai = _make_aai_mock()
        with patch("wx4.transcribe_aai.aai", mock_aai):
            from wx4.transcribe_aai import transcribe_assemblyai

            transcribe_assemblyai(tmp_path / "audio.wav", lang=None)
        kw = mock_aai.TranscriptionConfig.call_args.kwargs
        assert kw["language_detection"] is True

    def test_raises_on_transcript_error_status(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ASSEMBLY_AI_KEY", "key")
        mock_aai = _make_aai_mock(status="error", error="bad audio")
        with patch("wx4.transcribe_aai.aai", mock_aai):
            from wx4.transcribe_aai import transcribe_assemblyai

            with pytest.raises(RuntimeError, match="bad audio"):
                transcribe_assemblyai(tmp_path / "audio.wav")

    def test_writes_json_file_with_words(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ASSEMBLY_AI_KEY", "key")
        audio = tmp_path / "audio.wav"
        mock_aai = _make_aai_mock()
        with patch("wx4.transcribe_aai.aai", mock_aai):
            from wx4.transcribe_aai import transcribe_assemblyai

            _, json_path = transcribe_assemblyai(audio)
        assert json_path.exists()
        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert isinstance(data, list)
        assert data[0]["text"] == "hello"

    def test_writes_txt_file_with_utterances(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ASSEMBLY_AI_KEY", "key")
        audio = tmp_path / "audio.wav"
        mock_aai = _make_aai_mock()
        with patch("wx4.transcribe_aai.aai", mock_aai):
            from wx4.transcribe_aai import transcribe_assemblyai

            txt_path, _ = transcribe_assemblyai(audio)
        assert txt_path.exists()
        assert "Speaker A" in txt_path.read_text(encoding="utf-8")

    def test_returns_tuple_txt_json(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ASSEMBLY_AI_KEY", "key")
        audio = tmp_path / "audio.wav"
        mock_aai = _make_aai_mock()
        with patch("wx4.transcribe_aai.aai", mock_aai):
            from wx4.transcribe_aai import transcribe_assemblyai

            result = transcribe_assemblyai(audio)
        assert isinstance(result, tuple)
        assert len(result) == 2
        txt_path, json_path = result
        assert txt_path.suffix == ".txt"
        assert json_path.suffix == ".json"

    def test_speakers_expected_passed_to_config(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ASSEMBLY_AI_KEY", "key")
        mock_aai = _make_aai_mock()
        with patch("wx4.transcribe_aai.aai", mock_aai):
            from wx4.transcribe_aai import transcribe_assemblyai

            transcribe_assemblyai(tmp_path / "audio.wav", speakers=3)
        kw = mock_aai.TranscriptionConfig.call_args.kwargs
        assert kw["speakers_expected"] == 3
