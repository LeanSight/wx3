import json
from pathlib import Path
import pytest
from wx41.wx4 import MediaOrchestrator
from wx41.context import PipelineConfig
from wx41.steps.transcribe import TranscribeConfig
from wx41.ui.interrupt import InterruptHandler
import dataclasses


def test_ctrl_c_marks_interrupted_and_saves_state(tmp_path, monkeypatch):
    audio = tmp_path / "test.m4a"
    audio.touch()
    config = PipelineConfig(settings={"transcribe": TranscribeConfig(backend="whisper")})
    state_file = tmp_path / ".wx41_state.json"

    outputs_written = {}

    def fake_whisper(src, **kw):
        txt = src.parent / f"{src.stem}_whisper.txt"
        jsn = src.parent / f"{src.stem}_whisper.json"
        txt.write_text("partial", encoding="utf-8")
        jsn.write_text("[]", encoding="utf-8")
        outputs_written["transcript_txt"] = txt
        outputs_written["transcript_json"] = jsn
        return txt, jsn
    monkeypatch.setattr("wx41.steps.transcribe.transcribe_whisper", fake_whisper)

    orchestrator = MediaOrchestrator(config, [], state_path=state_file)

    ctx = orchestrator.run(audio)

    assert ctx.interrupted is False, "ctx.interrupted should be False for normal run"

    handler = InterruptHandler(state_file)
    test_ctx = dataclasses.replace(
        ctx, 
        outputs=outputs_written,
        timings={"transcribe": 1.5}
    )
    handler.install(test_ctx)
    try:
        handler._handle(None, None)
    except KeyboardInterrupt:
        pass

    assert state_file.exists(), f"State file must exist at {state_file}"
    state = json.loads(state_file.read_text(encoding="utf-8"))
    assert "src" in state, "State must contain 'src'"
    assert "outputs" in state, "State must contain 'outputs'"
    assert state["outputs"]["transcript_txt"].endswith(".txt")
