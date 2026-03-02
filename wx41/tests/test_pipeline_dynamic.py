from pathlib import Path
import pytest
from wx41.pipeline import MediaOrchestrator
from wx41.context import PipelineConfig
from wx41.steps.transcribe import TranscribeConfig


def test_pipeline_reads_steps_from_config_settings(tmp_path, monkeypatch):
    audio = tmp_path / "test.m4a"
    audio.touch()

    def fake_whisper(src, **kw):
        txt = src.parent / f"{src.stem}_whisper.txt"
        jsn = src.parent / f"{src.stem}_whisper.json"
        txt.write_text("ok", encoding="utf-8")
        jsn.write_text("[]", encoding="utf-8")
        return txt, jsn
    monkeypatch.setattr("wx41.steps.transcribe.transcribe_whisper", fake_whisper)

    config = PipelineConfig(settings={
        "transcribe": TranscribeConfig(backend="whisper")
    })
    orchestrator = MediaOrchestrator(config, [])
    ctx = orchestrator.run(audio)

    assert "transcript_txt" in ctx.outputs, (
        f"Expected 'transcript_txt' in outputs, got: {ctx.outputs.keys()}"
    )
    assert ctx.outputs["transcript_txt"].exists()
