import io
from pathlib import Path
import pytest
from wx41.wx4 import MediaOrchestrator
from wx41.context import PipelineConfig
from wx41.steps.transcribe import TranscribeConfig
from wx41.ui.progress import ProgressConsole


def test_ui_shows_step_name_during_run(tmp_path, monkeypatch):
    audio = tmp_path / "test.m4a"
    audio.touch()
    config = PipelineConfig(settings={"transcribe": TranscribeConfig(backend="whisper")})

    def fake_whisper(src, **kw):
        txt = src.parent / f"{src.stem}_whisper.txt"
        jsn = src.parent / f"{src.stem}_whisper.json"
        txt.write_text("ok", encoding="utf-8")
        jsn.write_text("[]", encoding="utf-8")
        return txt, jsn
    monkeypatch.setattr("wx41.steps.transcribe.transcribe_whisper", fake_whisper)

    out = io.StringIO()
    observer = ProgressConsole(out)
    orchestrator = MediaOrchestrator(config, [observer])
    orchestrator.run(audio)

    output = out.getvalue()
    assert "transcribe" in output.lower(), (
        f"Expected 'transcribe' in UI output, but got: {output}"
    )
