from pathlib import Path
import pytest
from wx41.steps.transcribe import transcribe_step, TranscribeConfig
from wx41.context import PipelineContext

class TestTranscribeStepModular:
    def test_transcribe_happy_path(self, audio_file, monkeypatch):
        # 1. Setup
        ctx = PipelineContext(src=audio_file)
        config = TranscribeConfig(backend="assemblyai")
        
        # Mock de la infraestructura
        txt_out = audio_file.parent / "audio_transcript.txt"
        jsn_out = audio_file.parent / "audio_timestamps.json"
        
        def fake_aai(*args, **kwargs):
            txt_out.write_text("hello", encoding="utf-8")
            jsn_out.write_text("[]", encoding="utf-8")
            return txt_out, jsn_out

        # Necesitaremos que el modulo exista para mockearlo
        import wx41.steps.transcribe
        monkeypatch.setattr("wx41.steps.transcribe.transcribe_assemblyai", fake_aai)

        # 2. Execution
        result_ctx = transcribe_step(ctx, config)

        # 3. Verification
        assert "transcript_txt" in result_ctx.outputs
        assert "transcript_json" in result_ctx.outputs
        assert result_ctx.outputs["transcript_txt"] == txt_out
