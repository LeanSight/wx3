from pathlib import Path
import pytest
from wx41.pipeline import MediaOrchestrator
from wx41.context import PipelineConfig
from wx41.steps.transcribe import TranscribeConfig


def test_resume_skips_existing_outputs(tmp_path, monkeypatch):
    audio = tmp_path / "test.m4a"
    audio.touch()
    config = PipelineConfig(settings={"transcribe": TranscribeConfig(backend="whisper")})
    transcribe_cfg = config.settings["transcribe"]

    call_count = {"n": 0}
    def fake_whisper(src, **kw):
        call_count["n"] += 1
        txt = src.parent / f"{src.stem}_whisper.txt"
        jsn = src.parent / f"{src.stem}_whisper.json"
        txt.write_text(f"call_{call_count['n']}", encoding="utf-8")
        jsn.write_text("[]", encoding="utf-8")
        return txt, jsn
    monkeypatch.setattr("wx41.steps.transcribe.transcribe_whisper", fake_whisper)

    orchestrator = MediaOrchestrator(config, [])

    ctx1 = orchestrator.run(audio)
    assert call_count["n"] == 1, f"Primera llamada debe ejecutar whisper, pero n={call_count['n']}"
    for key in transcribe_cfg.output_keys:
        assert ctx1.outputs[key].exists(), f"{key} debe existir despues de primer run"

    original_content = ctx1.outputs[transcribe_cfg.output_keys[0]].read_text(encoding="utf-8")

    ctx2 = orchestrator.run(audio, resume=True)
    assert call_count["n"] == 1, (
        f"Segunda llamada con resume=True no debe ejecutar whisper, pero n={call_count['n']}"
    )
    for key in transcribe_cfg.output_keys:
        assert ctx2.outputs[key].exists(), f"{key} debe existir en resume"

    resumed_content = ctx2.outputs[transcribe_cfg.output_keys[0]].read_text(encoding="utf-8")
    assert resumed_content == original_content, (
        f"Contenido debe ser igual en resume: {resumed_content!r} != {original_content!r}"
    )
