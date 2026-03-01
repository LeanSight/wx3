from pathlib import Path
import pytest
from wx41.pipeline import MediaOrchestrator
from wx41.context import PipelineConfig
from wx41.steps.transcribe import TranscribeConfig

class TestPipelineWalkingSkeleton:
    def test_produces_transcript_files_with_whisper(self, audio_file):
        backend = "whisper"
        
        config = PipelineConfig(
            settings={"transcribe": TranscribeConfig(backend=backend)}
        )
        transcribe_cfg = config.settings["transcribe"]
        
        orchestrator = MediaOrchestrator(config, [])
        ctx = orchestrator.run(audio_file)

        for key in transcribe_cfg.output_keys:
            assert key in ctx.outputs, f"{key} not in outputs"
            assert ctx.outputs[key].exists(), f"Output file not found: {key}"
            content = ctx.outputs[key].read_text(encoding="utf-8")
            assert len(content) > 0, f"Output file is empty: {key}"
