"""
ATDD acceptance scenarios for the wx4 pipeline.
All mocked at ffmpeg + assemblyai boundaries.
Written first (RED). Will go GREEN after all modules are implemented.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestAcceptance:
    def test_full_pipeline_audio_to_srt(self, tmp_path):
        """Pipeline completo: audio -> enhanced M4A -> JSON+TXT -> SRT."""
        src = tmp_path / "meeting.mp3"
        src.write_bytes(b"fake audio")

        words = [
            {"text": "hello", "start": 0, "end": 500, "speaker": "A"},
            {"text": "world.", "start": 500, "end": 1000, "speaker": "A"},
        ]
        json_path = tmp_path / "meeting_enhanced_timestamps.json"
        txt_path = tmp_path / "meeting_enhanced_transcript.txt"
        json_path.write_text(json.dumps(words), encoding="utf-8")
        txt_path.write_text("[00:00] Speaker A: hello world.", encoding="utf-8")

        enhanced_path = tmp_path / "meeting_enhanced.m4a"
        enhanced_path.write_bytes(b"enhanced audio")

        with (
            patch("wx4.audio_extract.ffmpeg"),
            patch("wx4.audio_normalize.ffmpeg"),
            patch("wx4.audio_normalize.shutil"),
            patch("wx4.audio_encode.ffmpeg"),
            patch("wx4.steps.extract_to_wav", return_value=True),
            patch("wx4.steps.normalize_lufs", return_value=True),
            patch("wx4.steps.apply_clearvoice", return_value=True),
            patch("wx4.steps.to_aac", return_value=True) as mock_aac,
            patch(
                "wx4.steps.transcribe_assemblyai", return_value=(txt_path, json_path)
            ),
        ):
            mock_aac.side_effect = lambda s, d, **kw: (
                d.write_bytes(b"aac") or True
            )

            from wx4.context import PipelineContext
            from wx4.pipeline import Pipeline, build_steps

            ctx = PipelineContext(src=src, output_m4a=True)
            ctx = ctx.__class__(
                src=src,
                output_m4a=True,
                enhanced=enhanced_path,
                cache_hit=False,
            )
            steps = build_steps(skip_enhance=True)
            pipeline = Pipeline(steps)
            result = pipeline.run(ctx)

        assert result.srt is not None
        assert isinstance(result.srt, Path)

    def test_skip_enhance_uses_src_directly(self, tmp_path):
        """skip_enhance=True => transcribe is called with src, not enhanced."""
        src = tmp_path / "audio.wav"
        src.write_bytes(b"raw audio")

        words = [{"text": "hi.", "start": 0, "end": 500, "speaker": "A"}]
        json_path = tmp_path / "audio_timestamps.json"
        txt_path = tmp_path / "audio_transcript.txt"
        json_path.write_text(json.dumps(words), encoding="utf-8")
        txt_path.write_text("text", encoding="utf-8")

        with patch(
            "wx4.steps.transcribe_assemblyai", return_value=(txt_path, json_path)
        ) as mock_transcribe:
            from wx4.context import PipelineContext
            from wx4.pipeline import Pipeline, build_steps

            ctx = PipelineContext(src=src, skip_enhance=True)
            steps = build_steps(skip_enhance=True)
            pipeline = Pipeline(steps)
            result = pipeline.run(ctx)

        call_audio = mock_transcribe.call_args[0][0]
        assert call_audio == src
        assert result.enhanced is None

    def test_cache_hit_skips_enhance(self, tmp_path):
        """Cache pre-populated -> apply_clearvoice is NOT called."""
        src = tmp_path / "meeting.mp3"
        src.write_bytes(b"audio")
        enhanced_path = tmp_path / "meeting_enhanced.m4a"
        enhanced_path.write_bytes(b"enhanced")

        words = [{"text": "test.", "start": 0, "end": 500, "speaker": "A"}]
        json_path = tmp_path / "meeting_enhanced_timestamps.json"
        txt_path = tmp_path / "meeting_enhanced_transcript.txt"
        json_path.write_text(json.dumps(words), encoding="utf-8")
        txt_path.write_text("text", encoding="utf-8")

        from wx4.cache_io import file_key

        cache_data = {file_key(src): {"output": enhanced_path.name}}

        with (
            patch("wx4.steps.apply_clearvoice") as mock_cv,
            patch(
                "wx4.steps.transcribe_assemblyai", return_value=(txt_path, json_path)
            ),
            patch("wx4.steps.load_cache", return_value=cache_data),
        ):
            from wx4.context import PipelineContext
            from wx4.pipeline import Pipeline, build_steps

            ctx = PipelineContext(src=src)
            steps = build_steps(skip_enhance=False)
            pipeline = Pipeline(steps)
            result = pipeline.run(ctx)

        mock_cv.assert_not_called()
        assert result.enhanced == enhanced_path

    def test_speaker_names_appear_in_srt(self, tmp_path):
        """speaker_names={'A': 'Marcel'} -> SRT contains '[Marcel]'."""
        src = tmp_path / "audio.mp3"
        src.write_bytes(b"audio")

        words = [
            {"text": "hello", "start": 0, "end": 500, "speaker": "A"},
            {"text": "world.", "start": 500, "end": 1000, "speaker": "A"},
        ]
        json_path = tmp_path / "audio_timestamps.json"
        txt_path = tmp_path / "audio_transcript.txt"
        json_path.write_text(json.dumps(words), encoding="utf-8")
        txt_path.write_text("text", encoding="utf-8")

        with patch(
            "wx4.steps.transcribe_assemblyai", return_value=(txt_path, json_path)
        ):
            from wx4.context import PipelineContext
            from wx4.pipeline import Pipeline, build_steps

            ctx = PipelineContext(
                src=src,
                skip_enhance=True,
                speaker_names={"A": "Marcel"},
                srt_mode="sentences",
            )
            steps = build_steps(skip_enhance=True)
            pipeline = Pipeline(steps)
            result = pipeline.run(ctx)

        assert result.srt is not None
        srt_content = result.srt.read_text(encoding="utf-8")
        assert "[Marcel]" in srt_content
        assert "[A]" not in srt_content

    def test_video_step_produces_mp4(self, tmp_path):
        """videooutput=True -> ctx.video_out is a Path with .mp4 extension."""
        src = tmp_path / "audio.mp3"
        src.write_bytes(b"audio")

        words = [{"text": "hi.", "start": 0, "end": 500, "speaker": "A"}]
        json_path = tmp_path / "audio_timestamps.json"
        txt_path = tmp_path / "audio_transcript.txt"
        json_path.write_text(json.dumps(words), encoding="utf-8")
        txt_path.write_text("text", encoding="utf-8")

        with (
            patch(
                "wx4.steps.transcribe_assemblyai", return_value=(txt_path, json_path)
            ),
            patch("wx4.steps.audio_to_black_video", return_value=True),
        ):
            from wx4.context import PipelineContext
            from wx4.pipeline import Pipeline, build_steps

            ctx = PipelineContext(src=src, skip_enhance=True, videooutput=True)
            steps = build_steps(skip_enhance=True, videooutput=True)
            pipeline = Pipeline(steps)
            result = pipeline.run(ctx)

        assert result.video_out is not None
        assert result.video_out.suffix == ".mp4"

    def test_pipeline_without_video_step(self, tmp_path):
        """videooutput=False (default) -> ctx.video_out is None."""
        src = tmp_path / "audio.mp3"
        src.write_bytes(b"audio")

        words = [{"text": "hi.", "start": 0, "end": 500, "speaker": "A"}]
        json_path = tmp_path / "audio_timestamps.json"
        txt_path = tmp_path / "audio_transcript.txt"
        json_path.write_text(json.dumps(words), encoding="utf-8")
        txt_path.write_text("text", encoding="utf-8")

        with patch(
            "wx4.steps.transcribe_assemblyai", return_value=(txt_path, json_path)
        ):
            from wx4.context import PipelineContext
            from wx4.pipeline import Pipeline, build_steps

            ctx = PipelineContext(src=src, skip_enhance=True, videooutput=False)
            steps = build_steps(skip_enhance=True, videooutput=False)
            pipeline = Pipeline(steps)
            result = pipeline.run(ctx)

        assert result.video_out is None
