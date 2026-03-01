from pathlib import Path
import pytest
from wx41.pipeline import MediaOrchestrator
from wx41.context import PipelineConfig

class TestPipelineWalkingSkeleton:
    def test_produces_transcript_files(self, audio_file, monkeypatch):
        # 1. Setup: Mock the infrastructure to avoid real API calls but simulate file creation
        def fake_transcribe(ctx, config):
            txt = ctx.src.parent / f"{ctx.src.stem}_transcript.txt"
            jsn = ctx.src.parent / f"{ctx.src.stem}_timestamps.json"
            txt.write_text("hello", encoding="utf-8")
            jsn.write_text("[]", encoding="utf-8")
            
            # The step is responsible for updating the generic outputs map
            new_outputs = {**ctx.outputs, "transcript_txt": txt, "transcript_json": jsn}
            from dataclasses import replace
            return replace(ctx, outputs=new_outputs)

        # We will mock the transcribe_step which we'll define later as a plug-in
        monkeypatch.setattr("wx41.steps.transcribe.transcribe_step", fake_transcribe)

        # 2. Execution
        config = PipelineConfig() # Generic config with empty settings for now
        orchestrator = MediaOrchestrator(config, [])
        ctx = orchestrator.run(audio_file)

        # 3. Assertions: Verification of the GENERIC outputs map
        assert "transcript_txt" in ctx.outputs, "transcript_txt missing from ctx.outputs"
        assert "transcript_json" in ctx.outputs, "transcript_json missing from ctx.outputs"
        
        assert ctx.outputs["transcript_txt"].exists(), f"File not created: {ctx.outputs['transcript_txt']}"
        assert ctx.outputs["transcript_json"].exists(), f"File not created: {ctx.outputs['transcript_json']}"
