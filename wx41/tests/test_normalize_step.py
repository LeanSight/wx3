from pathlib import Path
import pytest
from wx41.pipeline import MediaOrchestrator
from wx41.context import PipelineConfig


def test_normalize_step_produces_normalized_output(tmp_path, monkeypatch):
    audio = tmp_path / "test.m4a"
    audio.touch()
    
    def fake_normalize(src, dst, **kw):
        dst.write_text("normalized_audio", encoding="utf-8")
        return True
    
    monkeypatch.setattr("wx41.audio_normalize.normalize_lufs", fake_normalize)
    
    from wx41.steps.normalize import NormalizeConfig
    config = PipelineConfig(settings={"normalize": NormalizeConfig()})
    
    orchestrator = MediaOrchestrator(config, [])
    ctx = orchestrator.run(audio)
    
    assert "normalized" in ctx.outputs, f"Expected 'normalized' in outputs, got: {ctx.outputs.keys()}"
    assert ctx.outputs["normalized"].exists(), f"Normalized file should exist"
    content = ctx.outputs["normalized"].read_text(encoding="utf-8")
    assert content == "normalized_audio", f"Expected 'normalized_audio', got: {content!r}"
