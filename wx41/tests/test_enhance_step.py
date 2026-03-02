from pathlib import Path
import pytest
from wx41.wx4 import MediaOrchestrator
from wx41.context import PipelineConfig


def test_enhance_step_produces_enhanced_output(tmp_path, monkeypatch):
    audio = tmp_path / "test.m4a"
    audio.touch()
    
    def fake_enhance(src, dst, **kw):
        dst.write_text("enhanced_audio", encoding="utf-8")
        return True
    
    import wx41.steps.enhance
    monkeypatch.setattr("wx41.steps.enhance.apply_clearvoice", fake_enhance)
    
    from wx41.steps.enhance import EnhanceConfig
    step_config = EnhanceConfig()
    config = PipelineConfig(settings={"enhance": step_config})
    
    orchestrator = MediaOrchestrator(config, [])
    ctx = orchestrator.run(audio)
    
    out_key = step_config.output_keys[0]
    assert out_key in ctx.outputs, f"Expected '{out_key}' in outputs, got: {ctx.outputs.keys()}"
    assert ctx.outputs[out_key].exists(), f"Enhanced file should exist"
    content = ctx.outputs[out_key].read_text(encoding="utf-8")
    assert content == "enhanced_audio", f"Expected 'enhanced_audio', got: {content!r}"
