from pathlib import Path
import pytest
from wx41.pipeline import MediaOrchestrator
from wx41.context import PipelineConfig

class TestPipelineWalkingSkeleton:
    def test_produces_transcript_files(self, audio_file, monkeypatch):
        # 1. Setup: Mock the builder to return a custom pipeline with a fake step
        import wx41.pipeline
        from wx41.pipeline import Pipeline, NamedStep
        
        def fake_transcribe(ctx):
            txt = ctx.src.parent / f"{ctx.src.stem}_transcript.txt"
            jsn = ctx.src.parent / f"{ctx.src.stem}_timestamps.json"
            txt.write_text("hello", encoding="utf-8")
            jsn.write_text("[]", encoding="utf-8")
            
            from dataclasses import replace
            new_outputs = {**ctx.outputs, "transcript_txt": txt, "transcript_json": jsn}
            return replace(ctx, outputs=new_outputs)

        def mock_build(config, observers):
            return Pipeline([NamedStep(name="transcribe", fn=fake_transcribe)], observers)

        monkeypatch.setattr(wx41.pipeline, "build_audio_pipeline", mock_build)

        # 2. Execution
        config = PipelineConfig()
        orchestrator = MediaOrchestrator(config, [])
        ctx = orchestrator.run(audio_file)

        # 3. Assertions
        assert "transcript_txt" in ctx.outputs
        assert "transcript_json" in ctx.outputs
        assert ctx.outputs["transcript_txt"].exists()
        assert ctx.outputs["transcript_json"].exists()
