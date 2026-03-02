from pathlib import Path
import pytest
from wx41.context import PipelineContext, PipelineConfig
from wx41.wx4 import MediaOrchestrator

def test_compress_step_produces_compressed_file(tmp_path, monkeypatch):
    video = tmp_path / "video.mp4"
    video.touch()
    
    from wx41.steps.compress import CompressConfig, compress_step
    step_config = CompressConfig(crf=28)
    
    ctx = PipelineContext(
        src=Path("original.m4a"),
        outputs={"video": video}
    )
    
    def fake_compress(in_path, out_path, **kwargs):
        out_path.write_text("compressed video", encoding="utf-8")
        return True
        
    import wx41.steps.compress
    monkeypatch.setattr("wx41.steps.compress.compress_video", fake_compress)
    
    result_ctx = compress_step(ctx, step_config)
    
    out_key = step_config.output_keys[0]
    assert out_key in result_ctx.outputs
    compressed_path = result_ctx.outputs[out_key]
    assert compressed_path.exists()
    assert "compressed" in compressed_path.name
