from pathlib import Path
import pytest
from wx41.pipeline import MediaOrchestrator
from wx41.context import PipelineConfig
from wx41.steps.transcribe import TranscribeConfig


def test_force_runs_even_when_outputs_exist(tmp_path, monkeypatch):
    audio = tmp_path / "test.m4a"
    audio.touch()

    existing_txt = tmp_path / "test_whisper.txt"
    existing_txt.write_text("existing_content", encoding="utf-8")
    existing_json = tmp_path / "test_whisper.json"
    existing_json.write_text("[]", encoding="utf-8")

    call_count = {"n": 0}
    def fake_whisper(src, **kw):
        call_count["n"] += 1
        txt = src.parent / f"{src.stem}_whisper.txt"
        jsn = src.parent / f"{src.stem}_whisper.json"
        txt.write_text("new_content", encoding="utf-8")
        jsn.write_text("[]", encoding="utf-8")
        return txt, jsn
    monkeypatch.setattr("wx41.steps.transcribe.transcribe_whisper", fake_whisper)

    config = PipelineConfig(settings={"transcribe": TranscribeConfig(backend="whisper")}, force=True)
    orchestrator = MediaOrchestrator(config, [])
    ctx = orchestrator.run(audio)

    assert call_count["n"] == 1, (
        f"With force=True, step should run even if outputs exist. Called {call_count['n']} times"
    )
    content = ctx.outputs["transcript_txt"].read_text(encoding="utf-8")
    assert content == "new_content", f"Expected new_content, got {content}"
