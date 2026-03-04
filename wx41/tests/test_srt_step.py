import json
from pathlib import Path
import pytest
from wx41.context import PipelineContext, PipelineConfig
from wx41.wx4 import MediaOrchestrator


def test_srt_step_produces_srt_file(tmp_path):
    audio = tmp_path / "audio.m4a"
    audio.touch()

    # Mock data for transcript
    words = [
        {"text": "Hola", "start": 0.0, "end": 1.0, "speaker": "A"},
        {"text": "mundo", "start": 1.5, "end": 2.5, "speaker": "A"},
    ]
    jsn_path = tmp_path / "audio_transcript.json"
    jsn_path.write_text(json.dumps(words), encoding="utf-8")

    from wx41.steps.srt import SRTConfig

    step_config = SRTConfig()

    # Setup context with the transcript file
    ctx = PipelineContext(src=audio, outputs={"transcript_json": jsn_path})

    config = PipelineConfig(settings={"srt": step_config})
    orchestrator = MediaOrchestrator(config, [])

    # We need to manually register the step if it hasn't been discovered yet
    # Or just rely on the Discovery if we created the file

    from wx41.steps.srt import srt_step

    result_ctx = srt_step(ctx, step_config)

    out_key = step_config.output_keys[0]
    assert out_key in result_ctx.outputs
    srt_path = result_ctx.outputs[out_key]
    assert srt_path.exists()

    content = srt_path.read_text(encoding="utf-8")
    assert "1" in content
    assert "00:00:00,000 --> 00:00:01,000" in content
    assert "Hola" in content
    assert "2" in content
    assert "00:00:01,500 --> 00:00:02,500" in content
    assert "mundo" in content


def test_srt_groups_consecutive_words_by_speaker(tmp_path):
    from wx41.steps.srt import srt_step, SRTConfig
    from wx41.context import PipelineContext

    json_path = tmp_path / "transcript.json"
    json_path.write_text(
        """[
        {"text": "Hello", "start": 0, "end": 500, "speaker": "A"},
        {"text": "world", "start": 500, "end": 1000, "speaker": "A"},
        {"text": "This", "start": 1500, "end": 2000, "speaker": "B"},
        {"text": "is", "start": 2000, "end": 2500, "speaker": "B"},
        {"text": "a", "start": 2500, "end": 2700, "speaker": "B"},
        {"text": "test", "start": 2700, "end": 3200, "speaker": "B"}
    ]""",
        encoding="utf-8",
    )

    audio = tmp_path / "audio.m4a"
    audio.touch()

    ctx = PipelineContext(
        src=audio,
        media_type="audio",
        force=False,
        dry_run=False,
        outputs={"transcript_json": json_path},
    )

    result = srt_step(ctx, SRTConfig(mode="sentences", max_chars=20))

    srt_path = result.outputs["srt"]
    srt_content = srt_path.read_text(encoding="utf-8")

    assert "Hello world" in srt_content, (
        f"SRT should group consecutive words. Got:\n{srt_content}"
    )

    entries = srt_content.strip().split("\n\n")
    assert len(entries) >= 2, (
        f"SRT should split into multiple entries. Got {len(entries)}:\n{srt_content}"
    )
