from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional
from pathlib import Path
import pytest


def test_step_info_holds_metadata():
    from wx41.steps import StepInfo
    
    @dataclass(frozen=True)
    class DummyConfig:
        output_keys: tuple = ("dummy_key",)
        
    info = StepInfo(
        name="dummy",
        config_class=DummyConfig,
        step_fn=lambda ctx, cfg: ctx,
        optional=True,
        description="A dummy step"
    )
    
    assert info.name == "dummy"
    assert info.optional is True
    assert info.config_class == DummyConfig
    assert info.description == "A dummy step"

def test_predict_output_path_follows_convention():
    from wx41.steps import predict_output_path
    
    src = Path("/tmp/audio.m4a")
    
    path = predict_output_path(src, "normalize", "normalized")
    assert path == Path("/tmp/audio_normalized.m4a")
    
    # Test with simplified suffix: transcribe_txt -> txt
    path_txt = predict_output_path(src, "transcribe", "transcribe_txt")
    assert path_txt == Path("/tmp/audio_txt.txt")
    
    # Test with different extension
    path_json = predict_output_path(src, "transcribe", "transcript_json")
    assert path_json == Path("/tmp/audio_transcript_json.json")
