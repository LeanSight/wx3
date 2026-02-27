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

    def test_video_step_uses_normalized_when_no_enhance(self, tmp_path):
        """--no-enhance: video_step debe usar ctx.normalized, no ctx.src."""
        src = tmp_path / "audio.mp3"
        src.write_bytes(b"audio")
        normalized = tmp_path / "audio_normalized.m4a"
        normalized.write_bytes(b"normalized")

        words = [{"text": "hi.", "start": 0, "end": 500, "speaker": "A"}]
        transcribe_mock = _make_transcribe_mock(tmp_path, "audio_normalized", words)

        with (
            patch("wx4.steps.transcribe_assemblyai", side_effect=transcribe_mock),
            patch("wx4.steps.audio_to_black_video") as m_video,
        ):
            from wx4.context import PipelineConfig, PipelineContext
            from wx4.pipeline import Pipeline, build_steps

            ctx = PipelineContext(src=src, normalized=normalized)
            steps = build_steps(PipelineConfig(skip_enhance=True, videooutput=True))
            pipeline = Pipeline(steps)
            result = pipeline.run(ctx)

        m_video.assert_called_once()
        audio_used = m_video.call_args[0][0]
        assert audio_used == normalized
        assert result.video_out is not None

    def test_video_output_with_compression(self, tmp_path):
        """videooutput=True + compress_ratio: genera video con audio mejorado + comprimido."""
        src = tmp_path / "audio.mp3"
        src.write_bytes(b"audio")
        enhanced = tmp_path / "audio_enhanced.m4a"
        enhanced.write_bytes(b"enhanced")

        mock_info = MagicMock()
        mock_info.has_audio = True
        compressed_path = tmp_path / "audio_enhanced_timestamps_compressed.mp4"
        compressed_path.write_bytes(b"video")

        with (
            patch("wx4.steps.audio_to_black_video", return_value=True) as m_video,
            patch("wx4.steps._compress_video", return_value=None),
            patch("wx4.steps.probe_video", return_value=mock_info),
            patch("wx4.steps.measure_audio_lufs", return_value=-20.0),
            patch("wx4.steps.LufsInfo") as mock_lufs,
            patch("wx4.steps.detect_best_encoder", return_value=MagicMock()),
            patch("wx4.steps.calculate_video_bitrate") as m_bitrate,
        ):
            mock_lufs.from_measured.return_value = MagicMock()
            mock_lufs.noop.return_value = MagicMock()
            m_bitrate.return_value = 500_000

            from wx4.context import PipelineContext
            from wx4.steps import video_step

            ctx = PipelineContext(
                src=src,
                enhanced=enhanced,
                compress_ratio=0.3,
            )
            result = video_step(ctx)

        m_video.assert_called_once()
        audio_used = m_video.call_args[0][0]
        assert audio_used == enhanced

        m_bitrate.assert_called_once_with(mock_info, 0.3)

        assert result.video_out is not None
        assert result.video_out.name.endswith("_timestamps.mp4")

    def test_compress_step_uses_enhanced_audio_when_exists(self, tmp_path):
        """compress_step debe usar *_enhanced.m4a si existe, no el audio del video original."""
        src = tmp_path / "meeting.mp4"
        src.write_bytes(b"fake video")
        enhanced = tmp_path / "meeting_enhanced.m4a"
        enhanced.write_bytes(b"enhanced audio")

        mock_info = MagicMock()
        mock_info.has_audio = True
        mock_lufs_cls = MagicMock()
        mock_lufs_cls.from_measured.return_value = MagicMock()
        mock_lufs_cls.noop.return_value = MagicMock()

        with (
            patch("wx4.steps.measure_audio_lufs") as m_lufs,
            patch("wx4.steps.probe_video", return_value=mock_info),
            patch("wx4.steps.LufsInfo", mock_lufs_cls),
            patch("wx4.steps.detect_best_encoder", return_value=MagicMock()),
            patch("wx4.steps.calculate_video_bitrate", return_value=500_000),
            patch("wx4.steps._compress_video"),
        ):
            from wx4.context import PipelineContext
            from wx4.steps import compress_step

            ctx = PipelineContext(src=src, enhanced=enhanced, compress_ratio=0.4)
            compress_step(ctx)

        m_lufs.assert_called_once_with(enhanced)

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

    def test_skipped_steps_populate_ctx_fields(self, tmp_path):
        """Cuando todos los intermedios existen, ctx tiene srt/transcript_json poblados."""
        src = tmp_path / "meeting.mp3"
        src.write_bytes(b"audio")
        json_path = tmp_path / "meeting_timestamps.json"
        json_path.write_text("[]", encoding="utf-8")
        srt_path = tmp_path / "meeting_timestamps.srt"
        srt_path.write_text("", encoding="utf-8")

        from wx4.context import PipelineConfig, PipelineContext
        from wx4.pipeline import Pipeline, build_steps

        ctx = PipelineContext(src=src)
        steps = build_steps(PipelineConfig(skip_enhance=True))
        pipeline = Pipeline(steps)
        result = pipeline.run(ctx)

        assert result.srt == srt_path
        assert result.transcript_json == json_path

    def test_normalize_skipped_when_enhanced_exists_on_disk(self, tmp_path):
        """Si _enhanced.m4a existe en disco, normalize NO debe correr (ni crear tmp files)."""
        src = tmp_path / "meeting.mp3"
        src.write_bytes(b"audio")
        enhanced = tmp_path / "meeting_enhanced.m4a"
        enhanced.write_bytes(b"enhanced")

        words = [{"text": "hi.", "start": 0, "end": 500, "speaker": "A"}]
        transcribe_mock = _make_transcribe_mock(tmp_path, "meeting_enhanced", words)

        with (
            patch("wx4.steps.extract_to_wav") as m_ext,
            patch("wx4.steps.normalize_lufs") as m_norm,
            patch("wx4.steps.transcribe_assemblyai", side_effect=transcribe_mock),
            patch("wx4.steps.load_cache", return_value={}),
        ):
            from wx4.context import PipelineConfig, PipelineContext
            from wx4.pipeline import Pipeline, build_steps

            ctx = PipelineContext(src=src)
            steps = build_steps(PipelineConfig())
            pipeline = Pipeline(steps)
            result = pipeline.run(ctx)

        m_ext.assert_not_called()
        m_norm.assert_not_called()
        assert result.enhanced == enhanced
        assert result.srt is not None

    def test_compress_step_skips_audio_only_source(self, tmp_path):
        """compress_ratio set but source is audio-only -> pipeline completes, video_compressed is None."""
        src = tmp_path / "meeting.m4a"
        src.write_bytes(b"audio")

        words = [{"text": "hi.", "start": 0, "end": 500, "speaker": "A"}]
        transcribe_mock = _make_transcribe_mock(tmp_path, "meeting", words)

        with (
            patch("wx4.steps.transcribe_assemblyai", side_effect=transcribe_mock),
            patch("wx4.steps.probe_video", side_effect=RuntimeError("no video stream")),
        ):
            from wx4.context import PipelineConfig, PipelineContext
            from wx4.pipeline import Pipeline, build_steps

            ctx = PipelineContext(src=src)
            steps = build_steps(PipelineConfig(skip_enhance=True, compress_ratio=0.4))
            pipeline = Pipeline(steps)
            result = pipeline.run(ctx)

        assert result.video_compressed is None
        assert result.srt is not None

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
    def test_get_model_importable_from_model_cache(self, tmp_path):
        """
        AT: _get_model debe ser importable desde wx4.model_cache.
        """
        from wx4.model_cache import _get_model

        calls = []
        result = _get_model("TestModel", lambda: calls.append(1) or "v1", None)
        assert result == "v1"
        assert len(calls) == 1

    def test_pipeline_context_has_no_cv_field(self, tmp_path):
        """
        AT: PipelineContext no debe tener campo cv (campo muerto eliminado).
        """
        from wx4.context import PipelineContext
        from pathlib import Path

        src = tmp_path / "audio.mp3"
        src.write_bytes(b"audio")
        ctx = PipelineContext(src=src)
        assert not hasattr(ctx, "cv")

    def test_cv_model_defined_in_steps_not_cli(self):
        """
        AT: _CV_MODEL debe estar en steps.py, no en cli.py.
        """
        import wx4.steps as steps
        import wx4.cli as cli

        assert hasattr(steps, "_CV_MODEL"), "_CV_MODEL should be in steps.py"
        assert not hasattr(cli, "_CV_MODEL"), "_CV_MODEL should NOT be in cli.py"

    def test_tmp_raw_tmp_norm_are_intermediate_files(self, tmp_path):
        """
        AT: Archivos con sufijos _tmp_raw y _tmp_norm deben ser ignorados.
        """
        from wx4.cli import _is_processable_file

        tmp_raw_file = tmp_path / "audio._tmp_raw.wav"
        tmp_raw_file.write_bytes(b"fake")
        assert _is_processable_file(tmp_raw_file) is False

        tmp_norm_file = tmp_path / "audio._tmp_norm.wav"
        tmp_norm_file.write_bytes(b"fake")
        assert _is_processable_file(tmp_norm_file) is False

        combined_file = tmp_path / "audio._tmp_raw._tmp_norm.wav"
        combined_file.write_bytes(b"fake")
        assert _is_processable_file(combined_file) is False

    def test_expand_paths_does_not_call_ffprobe(self, tmp_path):
        """
        AT: _expand_paths no debe llamar a ffprobe - usa whitelist de extensiones.
        """
        from wx4.cli import _expand_paths

        (tmp_path / "video.mp4").write_bytes(b"fake")
        (tmp_path / "audio.m4a").write_bytes(b"fake")
        (tmp_path / "audio.mp3").write_bytes(b"fake")
        (tmp_path / "doc.pdf").write_bytes(b"fake")

        with patch("wx4.cli.ffmpeg.probe") as mock_probe:
            result = _expand_paths([str(tmp_path)])
            mock_probe.assert_not_called()

        assert len(result) == 3
        assert all(p.suffix in {".mp4", ".m4a", ".mp3"} for p in result)

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
            patch("wx4.steps._load_clearvoice", return_value=MagicMock()),
        ):
            from wx4.context import PipelineConfig, PipelineContext
            from wx4.pipeline import Pipeline, build_steps

            ctx = PipelineContext(src=src)
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


# ---------------------------------------------------------------------------
# AT: normalize_step progress reporting
# ---------------------------------------------------------------------------


class TestNormalizeProgress:
    def test_normalize_step_calls_step_progress(self, tmp_path):
        """
        AT: normalize_step llama step_progress al menos una vez cuando normaliza.
        """
        from pathlib import Path
        from unittest.mock import patch, MagicMock

        from wx4.context import PipelineContext
        from wx4.steps import normalize_step

        src = tmp_path / "meeting.mp3"
        src.write_bytes(b"fake audio")

        progress_calls = []

        def _capture_progress(done, total):
            progress_calls.append((done, total))

        def fake_to_aac(src, dst, **kw):
            dst.write_bytes(b"aac")
            return True

        def fake_normalize_lufs(src, dst, progress_callback=None):
            if progress_callback:
                progress_callback(50, 100)
            return True

        ctx = PipelineContext(
            src=src,
            output_m4a=True,
            step_progress=_capture_progress,
        )

        with (
            patch("wx4.steps.extract_to_wav", return_value=True),
            patch("wx4.steps.normalize_lufs", side_effect=fake_normalize_lufs),
            patch("wx4.steps.to_aac", side_effect=fake_to_aac),
        ):
            normalize_step(ctx)

        assert len(progress_calls) >= 1
        assert all(0 <= d <= t for d, t in progress_calls)

    def test_normalize_step_reports_milestones(self, tmp_path):
        """
        AT: normalize_step llama step_progress en al menos 2 momentos distintos.
        """
        from pathlib import Path
        from unittest.mock import patch, MagicMock

        from wx4.context import PipelineContext
        from wx4.steps import normalize_step

        src = tmp_path / "meeting.mp3"
        src.write_bytes(b"fake audio")

        progress_calls = []

        def _capture_progress(done, total):
            progress_calls.append((done, total))

        def fake_to_aac(src, dst, **kw):
            dst.write_bytes(b"aac")
            return True

        def fake_normalize_lufs(src, dst, progress_callback=None):
            if progress_callback:
                progress_callback(50, 100)
            return True

        ctx = PipelineContext(
            src=src,
            output_m4a=True,
            step_progress=_capture_progress,
        )

        with (
            patch("wx4.steps.extract_to_wav", return_value=True),
            patch("wx4.steps.normalize_lufs", side_effect=fake_normalize_lufs),
            patch("wx4.steps.to_aac", side_effect=fake_to_aac),
        ):
            normalize_step(ctx)

        assert len(progress_calls) >= 2


class TestUIBehavior:
    """ATDD tests for UI behavior - filename in header, progress bars, etc."""

    def test_live_display_includes_filename(self, tmp_path):
        """Filename should appear in the Live display header."""
        from pathlib import Path
        from unittest.mock import MagicMock
        from wx4.cli import RichProgressCallback
        from wx4.context import PipelineContext

        console = MagicMock()
        progress = MagicMock()
        cb = RichProgressCallback(console, progress)

        src = Path("/test/audio.mp3")
        ctx = PipelineContext(src=src)

        cb.on_pipeline_start(["cache_check", "enhance"], ctx)
        tree = cb._render_tree()

        assert "audio.mp3" in tree.plain

        cb._live.stop()


def test_progress_widget_has_bar_column():
    """Progress widget should include BarColumn for visual progress."""
    from rich.progress import BarColumn, TimeElapsedColumn
    from unittest.mock import MagicMock

    from wx4.cli import _make_progress

    console = MagicMock()
    progress = _make_progress(console)

    assert any(isinstance(c, BarColumn) for c in progress.columns)
    assert any(isinstance(c, TimeElapsedColumn) for c in progress.columns)


def test_progress_task_has_empty_description():
    """Progress task should have empty description to avoid duplication with tree."""
    from unittest.mock import MagicMock

    from wx4.cli import RichProgressCallback
    from wx4.context import PipelineContext

    console = MagicMock()
    progress = MagicMock()
    cb = RichProgressCallback(console, progress)

    ctx = PipelineContext(src=MagicMock())
    cb.on_pipeline_start(["compress"], ctx)
    try:
        cb.on_step_start("compress", ctx)

        call_args = progress.add_task.call_args
        assert call_args.kwargs.get("description") == "" or call_args.args[0] == ""
    finally:
        cb._live.stop()


def test_running_step_renders_colored_icon():
    """Regression test: colored icons must render as ANSI, not as literal [cyan] tags."""
    from io import StringIO
    from pathlib import Path
    from rich.console import Console

    from wx4.cli import RichProgressCallback
    from wx4.context import PipelineContext

    buf = StringIO()
    console = Console(file=buf, force_terminal=True, width=80)
    progress = MagicMock()
    progress.add_task = MagicMock(return_value=1)
    cb = RichProgressCallback(console, progress)

    ctx = PipelineContext(src=Path("/test/audio.mp3"))
    cb.on_pipeline_start(["enhance"], ctx)
    try:
        cb._step_states["enhance"] = "running"
        cb._progress_task = None

        tree = cb._render_tree()
        console.print(tree)

        output = buf.getvalue()
        assert "[cyan]" not in output
        assert ">" in output
    finally:
        cb._live.stop()
