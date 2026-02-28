from pathlib import Path

from wx41.context import PipelineConfig
from wx41.pipeline import MediaOrchestrator


class TestPipelineWalkingSkeleton:
    def test_produces_transcript_files(self, tmp_path, monkeypatch):
        src = tmp_path / "audio.m4a"
        src.touch()
        txt = tmp_path / "audio_transcript.txt"
        jsn = tmp_path / "audio_timestamps.json"

        def fake_transcribe(*a, **kw):
            txt.write_text("hello", encoding="utf-8")
            jsn.write_text("[]", encoding="utf-8")
            return txt, jsn

        monkeypatch.setattr(
            "wx41.steps.transcribe.transcribe_assemblyai",
            fake_transcribe,
        )

        config = PipelineConfig()
        orchestrator = MediaOrchestrator(config, [])
        ctx = orchestrator.run(src)

        assert ctx.transcript_txt is not None, "transcript_txt no seteado en ctx"
        assert ctx.transcript_json is not None, "transcript_json no seteado en ctx"
        assert ctx.transcript_txt.exists(), f"archivo no creado: {ctx.transcript_txt}"
        assert ctx.transcript_json.exists(), f"archivo no creado: {ctx.transcript_json}"
