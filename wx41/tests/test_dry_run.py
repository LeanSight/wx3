from pathlib import Path
import pytest
from wx41.pipeline import MediaOrchestrator
from wx41.context import PipelineConfig
from wx41.steps.transcribe import TranscribeConfig


def test_dry_run_no_execution(tmp_path, monkeypatch):
    audio = tmp_path / "test.m4a"
    audio.touch()
    config = PipelineConfig(settings={"transcribe": TranscribeConfig(backend="whisper")})
    transcribe_cfg = config.settings["transcribe"]

    call_count = {"n": 0}
    def fake_whisper(src, **kw):
        call_count["n"] += 1
        txt = src.parent / f"{src.stem}_whisper.txt"
        jsn = src.parent / f"{src.stem}_whisper.json"
        txt.write_text("ok", encoding="utf-8")
        jsn.write_text("[]", encoding="utf-8")
        return txt, jsn
    monkeypatch.setattr("wx41.steps.transcribe.transcribe_whisper", fake_whisper)

    orchestrator = MediaOrchestrator(config, [])
    ctx = orchestrator.run(audio, dry_run=True)

    assert call_count["n"] == 0, (
        f"Se esperaba 0 llamadas a whisper en dry_run, pero hubo {call_count['n']}"
    )
    for key in transcribe_cfg.output_keys:
        assert key not in ctx.outputs, (
            f"{key} no debe estar en ctx.outputs en dry run, pero estaba: {ctx.outputs}"
        )
    assert ctx.dry_run is True, f"ctx.dry_run debe ser True, pero era {ctx.dry_run}"
