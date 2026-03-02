from pathlib import Path
import pytest
from wx41.wx4 import MediaOrchestrator
from wx41.context import PipelineConfig

def test_media_orchestrator_detects_audio_type(tmp_path):
    audio = tmp_path / "test.mp3"
    audio.touch()
    
    orchestrator = MediaOrchestrator(PipelineConfig(), [])
    ctx = orchestrator.run(audio, dry_run=True)
    
    assert hasattr(ctx, "media_type"), "Context should have media_type field"
    assert ctx.media_type == "audio"

def test_media_orchestrator_chooses_correct_sequence_for_audio(tmp_path):
    from wx41.wx4 import build_audio_pipeline
    from wx41.steps.normalize import NormalizeConfig
    from wx41.steps.enhance import EnhanceConfig
    from wx41.steps.transcribe import TranscribeConfig
    from wx41.steps.srt import SRTConfig
    from wx41.steps.black_video import BlackVideoConfig
    
    config = PipelineConfig(settings={
        "normalize": NormalizeConfig(),
        "enhance": EnhanceConfig(),
        "transcribe": TranscribeConfig(),
        "srt": SRTConfig(),
        "black_video": BlackVideoConfig()
    })
    
    pipeline = build_audio_pipeline(config, [])
    names = [s.name for s in pipeline._steps]
    assert names == ["normalize", "enhance", "transcribe", "srt", "black_video"]

def test_media_orchestrator_chooses_correct_sequence_for_video(tmp_path):
    from wx41.wx4 import build_video_pipeline
    from wx41.steps.normalize import NormalizeConfig
    from wx41.steps.enhance import EnhanceConfig
    from wx41.steps.transcribe import TranscribeConfig
    from wx41.steps.srt import SRTConfig
    from wx41.steps.compress import CompressConfig
    
    config = PipelineConfig(settings={
        "normalize": NormalizeConfig(),
        "enhance": EnhanceConfig(),
        "transcribe": TranscribeConfig(),
        "srt": SRTConfig(),
        "compress": CompressConfig()
    })
    
    pipeline = build_video_pipeline(config, [])
    names = [s.name for s in pipeline._steps]
    # Per user: normalize -> enhance -> transcribe -> srt -> compress
    assert names == ["normalize", "enhance", "transcribe", "srt", "compress"]
