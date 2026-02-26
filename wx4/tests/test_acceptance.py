"""
ATDD acceptance scenarios for the wx4 pipeline.
All mocked at ffmpeg + assemblyai boundaries.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def _make_transcribe_mock(tmp_path, stem, words=None):
    """
    Return a side_effect function that creates transcript files on disk
    (mimicking real transcribe_assemblyai) so skip logic sees no pre-existing output.
    """
    if words is None:
        words = [{"text": "hello", "start": 0, "end": 500, "speaker": "A"}]
    json_path = tmp_path / f"{stem}_timestamps.json"
    txt_path = tmp_path / f"{stem}_transcript.txt"

    def _side_effect(audio, lang=None, speakers=None):
        json_path.write_text(json.dumps(words), encoding="utf-8")
        txt_path.write_text("[00:00] Speaker A: hello", encoding="utf-8")
        return txt_path, json_path

    return _side_effect


class TestAcceptance:
    def test_full_pipeline_audio_to_srt(self, tmp_path):
        """Pipeline completo: audio -> enhanced M4A -> JSON+TXT -> SRT."""
        src = tmp_path / "meeting.mp3"
        src.write_bytes(b"fake audio")

        words = [
            {"text": "hello", "start": 0, "end": 500, "speaker": "A"},
            {"text": "world.", "start": 500, "end": 1000, "speaker": "A"},
        ]
        enhanced_path = tmp_path / "meeting_enhanced.m4a"

        transcribe_mock = _make_transcribe_mock(tmp_path, "meeting_enhanced", words)

        with (
            patch("wx4.steps.extract_to_wav", return_value=True),
            patch("wx4.steps.normalize_lufs", return_value=True),
            patch("wx4.steps.apply_clearvoice", return_value=True),
            patch(
                "wx4.steps.to_aac",
                side_effect=lambda s, d, **kw: d.write_bytes(b"aac") or True,
            ),
            patch("wx4.steps.transcribe_assemblyai", side_effect=transcribe_mock),
        ):
            from wx4.context import PipelineConfig, PipelineContext
            from wx4.pipeline import Pipeline, build_steps

            ctx = PipelineContext(
                src=src,
                output_m4a=True,
                enhanced=enhanced_path,
                cache_hit=False,
            )
            steps = build_steps(PipelineConfig(skip_enhance=True))
            pipeline = Pipeline(steps)
            result = pipeline.run(ctx)

        assert result.srt is not None
        assert isinstance(result.srt, Path)

    def test_skip_enhance_uses_src_directly(self, tmp_path):
        """skip_enhance=True => transcribe is called with src, not enhanced."""
        src = tmp_path / "audio.wav"
        src.write_bytes(b"raw audio")

        words = [{"text": "hi.", "start": 0, "end": 500, "speaker": "A"}]
        transcribe_mock = _make_transcribe_mock(tmp_path, "audio", words)

        with patch(
            "wx4.steps.transcribe_assemblyai", side_effect=transcribe_mock
        ) as mock_transcribe:
            from wx4.context import PipelineConfig, PipelineContext
            from wx4.pipeline import Pipeline, build_steps

            ctx = PipelineContext(src=src)
            steps = build_steps(PipelineConfig(skip_enhance=True))
            pipeline = Pipeline(steps)
            result = pipeline.run(ctx)

        call_audio = mock_transcribe.call_args[0][0]
        assert call_audio == src
        assert result.enhanced is None

    def test_cache_hit_skips_enhance(self, tmp_path):
        """Cache pre-populated -> apply_clearvoice is NOT called."""
        src = tmp_path / "meeting.mp3"
        src.write_bytes(b"audio")
        normalized_path = tmp_path / "meeting_normalized.m4a"
        normalized_path.write_bytes(b"normalized")
        enhanced_path = tmp_path / "meeting_enhanced.m4a"
        enhanced_path.write_bytes(b"enhanced")

        words = [{"text": "test.", "start": 0, "end": 500, "speaker": "A"}]
        transcribe_mock = _make_transcribe_mock(tmp_path, "meeting_enhanced", words)

        from wx4.cache_io import file_key

        cache_data = {file_key(src): {"output": enhanced_path.name}}

        with (
            patch("wx4.steps.apply_clearvoice") as mock_cv,
            patch("wx4.steps.transcribe_assemblyai", side_effect=transcribe_mock),
            patch("wx4.steps.load_cache", return_value=cache_data),
        ):
            from wx4.context import PipelineConfig, PipelineContext
            from wx4.pipeline import Pipeline, build_steps

            ctx = PipelineContext(src=src)
            steps = build_steps(PipelineConfig(skip_enhance=False))
            pipeline = Pipeline(steps)
            result = pipeline.run(ctx)

        mock_cv.assert_not_called()
        assert result.normalized == normalized_path
        assert result.enhanced == enhanced_path

    def test_speaker_names_appear_in_srt(self, tmp_path):
        """speaker_names={'A': 'Marcel'} -> SRT contains '[Marcel]'."""
        src = tmp_path / "audio.mp3"
        src.write_bytes(b"audio")

        words = [
            {"text": "hello", "start": 0, "end": 500, "speaker": "A"},
            {"text": "world.", "start": 500, "end": 1000, "speaker": "A"},
        ]
        transcribe_mock = _make_transcribe_mock(tmp_path, "audio", words)

        with patch("wx4.steps.transcribe_assemblyai", side_effect=transcribe_mock):
            from wx4.context import PipelineConfig, PipelineContext
            from wx4.pipeline import Pipeline, build_steps

            ctx = PipelineContext(
                src=src,
                speaker_names={"A": "Marcel"},
                srt_mode="sentences",
            )
            steps = build_steps(PipelineConfig(skip_enhance=True))
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
        transcribe_mock = _make_transcribe_mock(tmp_path, "audio", words)

        with (
            patch("wx4.steps.transcribe_assemblyai", side_effect=transcribe_mock),
            patch("wx4.steps.audio_to_black_video", return_value=True),
        ):
            from wx4.context import PipelineConfig, PipelineContext
            from wx4.pipeline import Pipeline, build_steps

            ctx = PipelineContext(src=src)
            steps = build_steps(PipelineConfig(skip_enhance=True, videooutput=True))
            pipeline = Pipeline(steps)
            result = pipeline.run(ctx)

        assert result.video_out is not None
        assert result.video_out.suffix == ".mp4"

    def test_compress_produces_video_compressed(self, tmp_path):
        """compress_ratio=0.4 -> result.video_compressed is Path named <stem>_compressed.mp4."""
        src = tmp_path / "meeting.mp4"
        src.write_bytes(b"fake video")

        words = [{"text": "hi.", "start": 0, "end": 500, "speaker": "A"}]
        transcribe_mock = _make_transcribe_mock(tmp_path, "meeting", words)

        mock_info = MagicMock()
        mock_info.has_audio = True
        mock_lufs_cls = MagicMock()
        mock_lufs_cls.from_measured.return_value = MagicMock()

        with (
            patch("wx4.steps.transcribe_assemblyai", side_effect=transcribe_mock),
            patch("wx4.steps.probe_video", return_value=mock_info),
            patch("wx4.steps.measure_audio_lufs", return_value=-20.0),
            patch("wx4.steps.LufsInfo", mock_lufs_cls),
            patch("wx4.steps.detect_best_encoder", return_value=MagicMock()),
            patch("wx4.steps.calculate_video_bitrate", return_value=500_000),
            patch("wx4.steps._compress_video"),
        ):
            from wx4.context import PipelineConfig, PipelineContext
            from wx4.pipeline import Pipeline, build_steps

            ctx = PipelineContext(src=src)
            steps = build_steps(PipelineConfig(skip_enhance=True, compress_ratio=0.4))
            pipeline = Pipeline(steps)
            result = pipeline.run(ctx)

        assert result.video_compressed is not None
        assert result.video_compressed.name == "meeting_compressed.mp4"

    def test_pipeline_without_compress_leaves_video_compressed_none(self, tmp_path):
        """compress_ratio=None (default) -> result.video_compressed is None."""
        src = tmp_path / "audio.mp3"
        src.write_bytes(b"audio")

        words = [{"text": "hi.", "start": 0, "end": 500, "speaker": "A"}]
        transcribe_mock = _make_transcribe_mock(tmp_path, "audio", words)

        with patch("wx4.steps.transcribe_assemblyai", side_effect=transcribe_mock):
            from wx4.context import PipelineConfig, PipelineContext
            from wx4.pipeline import Pipeline, build_steps

            ctx = PipelineContext(src=src)
            steps = build_steps(PipelineConfig(skip_enhance=True, compress_ratio=None))
            pipeline = Pipeline(steps)
            result = pipeline.run(ctx)

        assert result.video_compressed is None

    def test_pipeline_without_video_step(self, tmp_path):
        """videooutput=False (default) -> ctx.video_out is None."""
        src = tmp_path / "audio.mp3"
        src.write_bytes(b"audio")

        words = [{"text": "hi.", "start": 0, "end": 500, "speaker": "A"}]
        transcribe_mock = _make_transcribe_mock(tmp_path, "audio", words)

        with patch("wx4.steps.transcribe_assemblyai", side_effect=transcribe_mock):
            from wx4.context import PipelineConfig, PipelineContext
            from wx4.pipeline import Pipeline, build_steps

            ctx = PipelineContext(src=src)
            steps = build_steps(PipelineConfig(skip_enhance=True, videooutput=False))
            pipeline = Pipeline(steps)
            result = pipeline.run(ctx)

        assert result.video_out is None


# ---------------------------------------------------------------------------
# AT: Whisper (wx3) backend integration
# ---------------------------------------------------------------------------


def _make_whisper_transcribe_mock(tmp_path, stem):
    """
    Side effect that simulates transcribe_with_whisper() creating output files.
    Output JSON is in AssemblyAI word-level format (start/end in ms).
    """
    words = [
        {
            "text": "hola",
            "start": 0,
            "end": 400,
            "confidence": 1.0,
            "speaker": "SPEAKER_00",
        },
        {
            "text": "mundo.",
            "start": 500,
            "end": 1000,
            "confidence": 1.0,
            "speaker": "SPEAKER_00",
        },
    ]
    json_path = tmp_path / f"{stem}_timestamps.json"
    txt_path = tmp_path / f"{stem}_transcript.txt"

    def _side_effect(
        audio,
        lang=None,
        speakers=None,
        hf_token=None,
        device="auto",
        whisper_model=None,
    ):
        json_path.write_text(json.dumps(words), encoding="utf-8")
        txt_path.write_text("[00:00] Speaker SPEAKER_00: hola mundo.", encoding="utf-8")
        return txt_path, json_path

    return _side_effect


class TestAcceptanceWhisperBackend:
    def test_whisper_backend_produces_srt(self, tmp_path):
        """
        AT-1: transcribe_backend='whisper' -> pipeline runs transcribe_with_whisper
        and produces a valid SRT file (same shape as AssemblyAI path).
        """
        src = tmp_path / "meeting.mp3"
        src.write_bytes(b"fake audio")
        transcribe_mock = _make_whisper_transcribe_mock(tmp_path, "meeting")

        with patch("wx4.steps.transcribe_with_whisper", side_effect=transcribe_mock):
            from wx4.context import PipelineConfig, PipelineContext
            from wx4.pipeline import Pipeline, build_steps

            ctx = PipelineContext(
                src=src,
                transcribe_backend="whisper",
                hf_token="hf_fake",
            )
            steps = build_steps(PipelineConfig(skip_enhance=True))
            pipeline = Pipeline(steps)
            result = pipeline.run(ctx)

        assert result.srt is not None
        assert result.srt.suffix == ".srt"
        srt_content = result.srt.read_text(encoding="utf-8")
        assert "hola" in srt_content

    def test_whisper_backend_calls_transcribe_with_whisper_not_assemblyai(
        self, tmp_path
    ):
        """
        AT-2: With backend='whisper', transcribe_assemblyai is NEVER called.
        """
        src = tmp_path / "meeting.mp3"
        src.write_bytes(b"fake audio")
        transcribe_mock = _make_whisper_transcribe_mock(tmp_path, "meeting")

        with (
            patch(
                "wx4.steps.transcribe_with_whisper", side_effect=transcribe_mock
            ) as mock_wh,
            patch("wx4.steps.transcribe_assemblyai") as mock_aai,
        ):
            from wx4.context import PipelineConfig, PipelineContext
            from wx4.pipeline import Pipeline, build_steps

            ctx = PipelineContext(
                src=src,
                transcribe_backend="whisper",
                hf_token="hf_fake",
            )
            steps = build_steps(PipelineConfig(skip_enhance=True))
            Pipeline(steps).run(ctx)

        mock_wh.assert_called_once()
        mock_aai.assert_not_called()

    def test_assemblyai_backend_unchanged(self, tmp_path):
        """
        AT-3: Default backend='assemblyai' -> transcribe_assemblyai is called, not whisper.
        """
        src = tmp_path / "meeting.mp3"
        src.write_bytes(b"fake audio")
        transcribe_mock = _make_transcribe_mock(tmp_path, "meeting")

        with (
            patch(
                "wx4.steps.transcribe_assemblyai", side_effect=transcribe_mock
            ) as mock_aai,
            patch("wx4.steps.transcribe_with_whisper") as mock_wh,
        ):
            from wx4.context import PipelineConfig, PipelineContext
            from wx4.pipeline import Pipeline, build_steps

            ctx = PipelineContext(src=src)  # default transcribe_backend="assemblyai"
            steps = build_steps(PipelineConfig(skip_enhance=True))
            Pipeline(steps).run(ctx)

        mock_aai.assert_called_once()
        mock_wh.assert_not_called()

    def test_whisper_backend_passes_context_params(self, tmp_path):
        """
        AT-4: language, speakers, hf_token, device, whisper_model are forwarded
        to transcribe_with_whisper.
        """
        src = tmp_path / "meeting.mp3"
        src.write_bytes(b"fake audio")
        transcribe_mock = _make_whisper_transcribe_mock(tmp_path, "meeting")

        with patch(
            "wx4.steps.transcribe_with_whisper", side_effect=transcribe_mock
        ) as mock_wh:
            from wx4.context import PipelineConfig, PipelineContext
            from wx4.pipeline import Pipeline, build_steps

            ctx = PipelineContext(
                src=src,
                transcribe_backend="whisper",
                language="es",
                speakers=2,
                hf_token="hf_secret",
                device="cpu",
                whisper_model="openai/whisper-large-v3",
            )
            Pipeline(build_steps(PipelineConfig(skip_enhance=True))).run(ctx)

        call_kwargs = mock_wh.call_args[1]
        assert call_kwargs.get("lang") == "es"
        assert call_kwargs.get("speakers") == 2
        assert call_kwargs.get("hf_token") == "hf_secret"
        assert call_kwargs.get("device") == "cpu"
        assert call_kwargs.get("whisper_model") == "openai/whisper-large-v3"

    def test_no_normalize_skips_normalize_step(self, tmp_path):
        """--no-normalize: normalize_step no corre, enhance_step (clearvoice) si."""
        src = tmp_path / "audio.mp3"
        src.write_bytes(b"audio")
        words = [{"text": "hi.", "start": 0, "end": 500, "speaker": "A"}]
        transcribe_mock = _make_transcribe_mock(tmp_path, "audio_enhanced", words)

        with (
            patch("wx4.steps.transcribe_assemblyai", side_effect=transcribe_mock),
            patch("wx4.steps.apply_clearvoice") as m_cv,
            patch("wx4.steps.normalize_lufs") as m_norm,
            patch("wx4.steps.extract_to_wav") as m_ext,
            patch(
                "wx4.steps.to_aac",
                side_effect=lambda s, d, **kw: d.write_bytes(b"aac") or True,
            ),
        ):
            from wx4.context import PipelineConfig, PipelineContext
            from wx4.pipeline import Pipeline, build_steps

            ctx = PipelineContext(src=src, cv=MagicMock())
            steps = build_steps(PipelineConfig(skip_normalize=True))
            result = Pipeline(steps).run(ctx)

        m_norm.assert_not_called()
        m_ext.assert_not_called()
        m_cv.assert_called_once()
        assert result.srt is not None

    def test_no_enhance_skips_clearvoice(self, tmp_path):
        """--no-enhance: clearvoice no corre, normalize si."""
        src = tmp_path / "audio.mp3"
        src.write_bytes(b"audio")
        words = [{"text": "hi.", "start": 0, "end": 500, "speaker": "A"}]
        transcribe_mock = _make_transcribe_mock(tmp_path, "audio_normalized", words)

        with (
            patch("wx4.steps.transcribe_assemblyai", side_effect=transcribe_mock),
            patch("wx4.steps.apply_clearvoice") as m_cv,
            patch("wx4.steps.extract_to_wav", return_value=True),
            patch("wx4.steps.normalize_lufs"),
            patch(
                "wx4.steps.to_aac",
                side_effect=lambda s, d, **kw: d.write_bytes(b"aac") or True,
            ),
        ):
            from wx4.context import PipelineConfig, PipelineContext
            from wx4.pipeline import Pipeline, build_steps

            ctx = PipelineContext(src=src)
            steps = build_steps(PipelineConfig(skip_enhance=True))
            result = Pipeline(steps).run(ctx)

        m_cv.assert_not_called()
        assert result.srt is not None
