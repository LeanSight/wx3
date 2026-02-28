from pathlib import Path
import pytest
from wx41.steps.transcribe import transcribe_step, TranscribeConfig
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
        cfg = TranscribeConfig(backend="assemblyai")
        txt = tmp_path / "audio_transcript.txt"
        jsn = tmp_path / "audio_timestamps.json"

        def fake(*a, **kw):
            txt.write_text("hello", encoding="utf-8")
            jsn.write_text("[]", encoding="utf-8")
            return txt, jsn

        monkeypatch.setattr("wx41.steps.transcribe.transcribe_assemblyai", fake)

        result = transcribe_step(ctx, cfg)

        assert result.transcript_txt == txt
        assert result.transcript_json == jsn

class TestTranscribeStepUsesEnhanced:
    def test_uses_enhanced_when_set(self, tmp_path, monkeypatch):
        enhanced = tmp_path / "audio_enhanced.m4a"
        enhanced.touch()
        ctx = make_ctx(tmp_path, enhanced=enhanced)
        cfg = TranscribeConfig()
        txt, jsn = _fake_files(tmp_path, "audio_enhanced")

        captured = []
        def fake_transcribe(audio, *a, **kw):
            captured.append(audio)
            return txt, jsn

        monkeypatch.setattr("wx41.steps.transcribe.transcribe_assemblyai", fake_transcribe)
        transcribe_step(ctx, cfg)
        assert captured[0] == enhanced

    def test_uses_src_when_enhanced_is_none(self, tmp_path, monkeypatch):
        ctx = make_ctx(tmp_path, enhanced=None)
        cfg = TranscribeConfig()
        txt, jsn = _fake_files(tmp_path, "audio")

        captured = []
        def fake_transcribe(audio, *a, **kw):
            captured.append(audio)
            return txt, jsn

        monkeypatch.setattr("wx41.steps.transcribe.transcribe_assemblyai", fake_transcribe)
        transcribe_step(ctx, cfg)
        assert captured[0] == ctx.src

class TestTranscribeStepBackend:
    def test_whisper_backend(self, tmp_path, monkeypatch):
        ctx = make_ctx(tmp_path)
        cfg = TranscribeConfig(backend="whisper")
        txt, jsn = _fake_files(tmp_path, "audio")

        captured = []
        def fake_whisper(audio, *a, **kw):
            captured.append(audio)
            return txt, jsn

        monkeypatch.setattr("wx41.steps.transcribe.transcribe_with_whisper", fake_whisper)
        result = transcribe_step(ctx, cfg)
        assert result.transcript_txt == txt

    def test_unknown_backend_raises(self, tmp_path, monkeypatch):
        ctx = make_ctx(tmp_path)
        cfg = TranscribeConfig(backend="unknown")
        with pytest.raises(RuntimeError, match="Unknown transcribe_backend"):
            transcribe_step(ctx, cfg)

class TestTranscribeStepTiming:
    def test_timing_recorded(self, tmp_path, monkeypatch):
        ctx = make_ctx(tmp_path)
        cfg = TranscribeConfig()
        txt, jsn = _fake_files(tmp_path, "audio")

        monkeypatch.setattr(
            "wx41.steps.transcribe.transcribe_assemblyai",
            lambda *a, **kw: (txt, jsn),
        )

        result = transcribe_step(ctx, cfg)
        assert "transcribe" in result.timings
        assert result.timings["transcribe"] >= 0
