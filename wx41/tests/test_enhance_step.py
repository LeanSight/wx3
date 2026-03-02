from pathlib import Path
import pytest
from wx41.pipeline import MediaOrchestrator
from wx41.context import PipelineConfig


def test_enhance_step_produces_enhanced_output(tmp_path, monkeypatch):
    audio = tmp_path / "test.m4a"
    audio.touch()
    
    def fake_enhance(src, dst, **kw):
        dst.write_text("enhanced_audio", encoding="utf-8")
        return True
    
    monkeypatch.setattr("wx41.audio_enhance.apply_clearvoice", fake_enhance)
    
    from wx41.steps.enhance import EnhanceConfig
    config = PipelineConfig(settings={"enhance": EnhanceConfig()})
    
    orchestrator = MediaOrchestrator(config, [])
    ctx = orchestrator.run(audio)
    
    assert "enhanced" in ctx.outputs, f"Expected 'enhanced' in outputs, got: {ctx.outputs.keys()}"
    assert ctx.outputs["enhanced"].exists(), f"Enhanced file should exist"
    content = ctx.outputs["enhanced"].read_text(encoding="utf-8")
    assert content == "enhanced_audio", f"Expected 'enhanced_audio', got: {content!r}"
