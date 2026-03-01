from pathlib import Path
import pytest
from wx41.pipeline import MediaOrchestrator
from wx41.context import PipelineConfig
from wx41.steps.transcribe import TranscribeConfig

class TestPipelineWalkingSkeleton:
    def test_produces_transcript_files_with_whisper(self, audio_file):
        config = PipelineConfig(
            settings={"transcribe": TranscribeConfig(backend="whisper")}
        )
        orchestrator = MediaOrchestrator(config, [])
        ctx = orchestrator.run(audio_file)

        assert "transcript_txt" in ctx.outputs, "transcript_txt not in outputs"
        assert "transcript_json" in ctx.outputs, "transcript_json not in outputs"
        
        txt_path = ctx.outputs["transcript_txt"]
        jsn_path = ctx.outputs["transcript_json"]
        
        assert txt_path.exists(), f"Transcript file not found: {txt_path}"
        assert jsn_path.exists(), f"Timestamps file not found: {jsn_path}"
        
        txt_content = txt_path.read_text(encoding="utf-8")
        assert len(txt_content) > 0, "Transcript file is empty"
        
        jsn_content = jsn_path.read_text(encoding="utf-8")
        assert len(jsn_content) > 0, "JSON file is empty"
