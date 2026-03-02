from pathlib import Path
import pytest
from wx41.context import PipelineContext, PipelineConfig
from wx41.wx4 import MediaOrchestrator

def test_black_video_step_produces_video_file(tmp_path, monkeypatch):
    audio = tmp_path / "audio_normalized.m4a"
    audio.touch()
    
    from wx41.steps.black_video import BlackVideoConfig, black_video_step
    step_config = BlackVideoConfig()
    
    ctx = PipelineContext(
        src=audio,
        outputs={"normalized": audio}
    )
    
    # Mock ffmpeg call or the infrastructure function
    def fake_ffmpeg(audio_path, video_path, **kwargs):
        video_path.write_text("simulated video", encoding="utf-8")
        return True
        
    import wx41.steps.black_video
    monkeypatch.setattr("wx41.steps.black_video.generate_black_video", fake_ffmpeg)
    
    result_ctx = black_video_step(ctx, step_config)
    
    out_key = step_config.output_keys[0]
    assert out_key in result_ctx.outputs
    video_path = result_ctx.outputs[out_key]
    assert video_path.exists()
    assert video_path.suffix == ".mp4"
