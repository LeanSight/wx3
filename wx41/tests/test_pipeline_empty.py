from pathlib import Path
import pytest
from wx41.wx4 import MediaOrchestrator
from wx41.context import PipelineConfig


def test_pipeline_with_no_settings_runs_empty(tmp_path):
    audio = tmp_path / "test.m4a"
    audio.touch()
    
    config = PipelineConfig(settings={})
    orchestrator = MediaOrchestrator(config, [])
    ctx = orchestrator.run(audio)
    
    assert ctx.outputs == {}, f"Expected empty outputs, got {ctx.outputs}"
