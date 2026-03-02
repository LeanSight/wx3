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
    
    import wx41.steps.normalize
    monkeypatch.setattr("wx41.steps.normalize.normalize_lufs", fake_normalize)
    
    from wx41.steps.normalize import NormalizeConfig
    step_config = NormalizeConfig()
    config = PipelineConfig(settings={"normalize": step_config})
    
    orchestrator = MediaOrchestrator(config, [])
    ctx = orchestrator.run(audio)
    
    out_key = step_config.output_keys[0]
    assert out_key in ctx.outputs, f"Expected '{out_key}' in outputs, got: {ctx.outputs.keys()}"
    assert ctx.outputs[out_key].exists(), f"Normalized file should exist"
    content = ctx.outputs[out_key].read_text(encoding="utf-8")
    assert content == "normalized_audio", f"Expected 'normalized_audio', got: {content!r}"
