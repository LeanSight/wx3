from pathlib import Path

import pytest

from wx41.steps.transcribe import transcribe_step
from wx41.tests.conftest import make_ctx


def _fake_files(tmp_path: Path, stem: str):
    txt = tmp_path / f"{stem}_transcript.txt"
    jsn = tmp_path / f"{stem}_timestamps.json"
    txt.write_text("hello", encoding="utf-8")
    jsn.write_text("[]", encoding="utf-8")
    return txt, jsn


class TestTranscribeStepWalkingSkeleton:
    def test_assemblyai_happy_path(self, tmp_path, monkeypatch):
        ctx = make_ctx(tmp_path)
        txt = tmp_path / "audio_transcript.txt"
        jsn = tmp_path / "audio_timestamps.json"

        def fake(*a, **kw):
            txt.write_text("hello", encoding="utf-8")
            jsn.write_text("[]", encoding="utf-8")
            return txt, jsn

        monkeypatch.setattr("wx41.steps.transcribe.transcribe_assemblyai", fake)

        result = transcribe_step(ctx)

        assert result.transcript_txt == txt, f"transcript_txt incorrecto: {result.transcript_txt}"
        assert result.transcript_json == jsn, f"transcript_json incorrecto: {result.transcript_json}"
        assert result.transcript_txt.exists(), f"archivo no creado: {result.transcript_txt}"
        assert result.transcript_json.exists(), f"archivo no creado: {result.transcript_json}"


class TestTranscribeStepUsesEnhanced:
    def test_uses_enhanced_when_set(self, tmp_path, monkeypatch):
        enhanced = tmp_path / "audio_enhanced.m4a"
        enhanced.touch()
        ctx = make_ctx(tmp_path, enhanced=enhanced)
        txt, jsn = _fake_files(tmp_path, "audio_enhanced")

        captured = []

        def fake_transcribe(audio, *a, **kw):
            captured.append(audio)
            return txt, jsn

        monkeypatch.setattr("wx41.steps.transcribe.transcribe_assemblyai", fake_transcribe)

        transcribe_step(ctx)

        assert captured[0] == enhanced, f"esperado enhanced como audio, recibido: {captured[0]}"

    def test_uses_src_when_enhanced_is_none(self, tmp_path, monkeypatch):
        ctx = make_ctx(tmp_path, enhanced=None)
        txt, jsn = _fake_files(tmp_path, "audio")

        captured = []

        def fake_transcribe(audio, *a, **kw):
            captured.append(audio)
            return txt, jsn

        monkeypatch.setattr("wx41.steps.transcribe.transcribe_assemblyai", fake_transcribe)

        transcribe_step(ctx)

        assert captured[0] == ctx.src, f"esperado src como audio, recibido: {captured[0]}"


class TestTranscribeStepTiming:
    def test_timing_recorded(self, tmp_path, monkeypatch):
        ctx = make_ctx(tmp_path)
        txt, jsn = _fake_files(tmp_path, "audio")

        monkeypatch.setattr(
            "wx41.steps.transcribe.transcribe_assemblyai",
            lambda *a, **kw: (txt, jsn),
        )

        result = transcribe_step(ctx)

        assert "transcribe" in result.timings, f"timings actuales: {result.timings}"
        assert result.timings["transcribe"] >= 0, f"timing invalido: {result.timings['transcribe']}"


class TestTranscribeStepBackend:
    def test_whisper_backend(self, tmp_path, monkeypatch):
        ctx = make_ctx(tmp_path, transcribe_backend="whisper")
        txt, jsn = _fake_files(tmp_path, "audio")

        captured = []

        def fake_whisper(audio, *a, **kw):
            captured.append(audio)
            return txt, jsn

        monkeypatch.setattr("wx41.steps.transcribe.transcribe_with_whisper", fake_whisper)

        result = transcribe_step(ctx)

        assert result.transcript_txt == txt, f"transcript_txt incorrecto: {result.transcript_txt}"
        assert result.transcript_json == jsn, f"transcript_json incorrecto: {result.transcript_json}"

    def test_unknown_backend_raises(self, tmp_path, monkeypatch):
        ctx = make_ctx(tmp_path, transcribe_backend="unknown_backend")

        with pytest.raises(RuntimeError, match="Unknown transcribe_backend"):
            transcribe_step(ctx)


