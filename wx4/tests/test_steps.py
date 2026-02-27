"""
Tests for wx4/steps.py - pipeline step functions.
All external calls are mocked via patch.
"""

import dataclasses
import json
from pathlib import Path
from unittest.mock import ANY, MagicMock, call, patch

import pytest

from wx4.context import PipelineContext


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ctx(tmp_path, **kwargs) -> PipelineContext:
    src = tmp_path / "audio.mp3"
    src.write_bytes(b"fake audio")
    return PipelineContext(src=src, **kwargs)


# ---------------------------------------------------------------------------
# TestCacheCheckStep
# ---------------------------------------------------------------------------


class TestCacheCheckStep:
    def test_miss_when_src_not_in_cache(self, tmp_path):
        ctx = _ctx(tmp_path)
        with patch("wx4.steps.load_cache", return_value={}):
            from wx4.steps import cache_check_step

            result = cache_check_step(ctx)
        assert result.cache_hit is False
        assert result.enhanced is None

    def test_hit_when_src_in_cache(self, tmp_path):
        ctx = _ctx(tmp_path)
        enhanced = tmp_path / "audio_enhanced.m4a"
        enhanced.write_bytes(b"enhanced")
        from wx4.cache_io import file_key

        cache_data = {file_key(ctx.src): {"output": enhanced.name}}
        with patch("wx4.steps.load_cache", return_value=cache_data):
            from wx4.steps import cache_check_step

            result = cache_check_step(ctx)
        assert result.cache_hit is True
        assert result.enhanced == enhanced

    def test_force_flag_causes_miss_even_if_in_cache(self, tmp_path):
        ctx = _ctx(tmp_path, force=True)
        enhanced = tmp_path / "audio_enhanced.m4a"
        enhanced.write_bytes(b"enhanced")
        from wx4.cache_io import file_key

        cache_data = {file_key(ctx.src): {"output": enhanced.name}}
        with patch("wx4.steps.load_cache", return_value=cache_data):
            from wx4.steps import cache_check_step

            result = cache_check_step(ctx)
        assert result.cache_hit is False

    def test_timing_recorded_in_context(self, tmp_path):
        ctx = _ctx(tmp_path)
        with patch("wx4.steps.load_cache", return_value={}):
            from wx4.steps import cache_check_step

            result = cache_check_step(ctx)
        assert "cache_check" in result.timings


# ---------------------------------------------------------------------------
# TestCacheSaveStep
# ---------------------------------------------------------------------------


class TestCacheSaveStep:
    def test_saves_when_enhanced_and_no_hit(self, tmp_path):
        enhanced = tmp_path / "audio_enhanced.m4a"
        enhanced.write_bytes(b"enhanced")
        ctx = _ctx(tmp_path, enhanced=enhanced, cache_hit=False)

        with (
            patch("wx4.steps.save_cache") as mock_save,
            patch("wx4.steps.file_key", return_value="fake-key"),
        ):
            from wx4.steps import cache_save_step

            cache_save_step(ctx)
        mock_save.assert_called_once()

    def test_skips_when_cache_hit_true(self, tmp_path):
        enhanced = tmp_path / "audio_enhanced.m4a"
        enhanced.write_bytes(b"enhanced")
        ctx = _ctx(tmp_path, enhanced=enhanced, cache_hit=True)

        with patch("wx4.steps.save_cache") as mock_save:
            from wx4.steps import cache_save_step

            cache_save_step(ctx)
        mock_save.assert_not_called()

    def test_skips_when_enhanced_is_none(self, tmp_path):
        ctx = _ctx(tmp_path, enhanced=None, cache_hit=False)

        with patch("wx4.steps.save_cache") as mock_save:
            from wx4.steps import cache_save_step

            cache_save_step(ctx)
        mock_save.assert_not_called()

    def test_timing_recorded(self, tmp_path):
        enhanced = tmp_path / "audio_enhanced.m4a"
        enhanced.write_bytes(b"enhanced")
        ctx = _ctx(tmp_path, enhanced=enhanced, cache_hit=False)

        with (
            patch("wx4.steps.save_cache"),
            patch("wx4.steps.file_key", return_value="k"),
        ):
            from wx4.steps import cache_save_step

            result = cache_save_step(ctx)
        assert "cache_save" in result.timings


# ---------------------------------------------------------------------------
# TestEnhanceStep
# ---------------------------------------------------------------------------


class TestEnhanceStep:
    def test_returns_cached_path_on_hit(self, tmp_path):
        enhanced = tmp_path / "audio_enhanced.m4a"
        ctx = _ctx(tmp_path, cache_hit=True, enhanced=enhanced)

        from wx4.steps import enhance_step

        result = enhance_step(ctx)
        assert result.enhanced == enhanced

    def test_calls_only_clearvoice_and_encode_on_miss(self, tmp_path):
        ctx = _ctx(tmp_path, cache_hit=False, output_m4a=True)
        mock_cv = MagicMock()

        def fake_to_aac(src, dst, **kw):
            dst.write_bytes(b"aac")
            return True

        with (
            patch("wx4.steps.apply_clearvoice") as m_cv,
            patch("wx4.steps.to_aac", side_effect=fake_to_aac),
            patch("wx4.steps.extract_to_wav") as m_ext,
            patch("wx4.steps.normalize_lufs") as m_norm,
            patch("wx4.steps._load_clearvoice", return_value=mock_cv),
        ):
            from wx4.steps import enhance_step

            result = enhance_step(ctx)

        m_ext.assert_not_called()
        m_norm.assert_not_called()
        m_cv.assert_called_once()
        assert result.enhanced is not None

    def test_raises_when_extract_fails(self, tmp_path):
        ctx = _ctx(tmp_path, cache_hit=False)

        with (
            patch("wx4.steps.extract_to_wav", return_value=False),
            patch("wx4.steps._load_clearvoice", return_value=MagicMock()),
        ):
            from wx4.steps import enhance_step

            with pytest.raises(RuntimeError):
                enhance_step(ctx)

    def test_raises_when_encode_fails(self, tmp_path):
        ctx = _ctx(tmp_path, cache_hit=False, output_m4a=True)

        with (
            patch("wx4.steps.extract_to_wav", return_value=True),
            patch("wx4.steps.normalize_lufs"),
            patch("wx4.steps.apply_clearvoice"),
            patch("wx4.steps.to_aac", return_value=False),
            patch("wx4.steps._load_clearvoice", return_value=MagicMock()),
        ):
            from wx4.steps import enhance_step

            with pytest.raises(RuntimeError):
                enhance_step(ctx)

    def test_timing_recorded(self, tmp_path):
        enhanced = tmp_path / "audio_enhanced.m4a"
        ctx = _ctx(tmp_path, cache_hit=True, enhanced=enhanced)

        from wx4.steps import enhance_step

        result = enhance_step(ctx)
        assert "enhance" in result.timings


# ---------------------------------------------------------------------------
# TestNormalizeStep
# ---------------------------------------------------------------------------


class TestCacheCheckStepDiskFallback:
    def test_detects_enhanced_on_disk_without_cache_entry(self, tmp_path):
        src = tmp_path / "audio.mp3"
        src.write_bytes(b"fake audio")
        enhanced = tmp_path / "audio_enhanced.m4a"
        enhanced.write_bytes(b"enhanced")

        with patch("wx4.steps.load_cache", return_value={}):
            from wx4.steps import cache_check_step

            result = cache_check_step(PipelineContext(src=src))

        assert result.cache_hit is True
        assert result.enhanced == enhanced

    def test_no_hit_when_enhanced_missing_from_disk_and_cache(self, tmp_path):
        src = tmp_path / "audio.mp3"
        src.write_bytes(b"fake audio")

        with patch("wx4.steps.load_cache", return_value={}):
            from wx4.steps import cache_check_step

            result = cache_check_step(PipelineContext(src=src))

        assert result.cache_hit is False
        assert result.enhanced is None


class TestNormalizeStep:
    def test_skips_when_cache_hit(self, tmp_path):
        ctx = _ctx(tmp_path, cache_hit=True)

        with patch("wx4.steps.extract_to_wav") as m_ext:
            from wx4.steps import normalize_step

            result = normalize_step(ctx)

        m_ext.assert_not_called()
        assert "normalize" in result.timings

    def test_calls_extract_normalize_encode(self, tmp_path):
        ctx = _ctx(tmp_path, cache_hit=False, output_m4a=True)

        def fake_to_aac(src, dst, **kw):
            dst.write_bytes(b"aac")
            return True

        with (
            patch("wx4.steps.extract_to_wav", return_value=True) as m_ext,
            patch("wx4.steps.normalize_lufs") as m_norm,
            patch("wx4.steps.to_aac", side_effect=fake_to_aac) as m_enc,
        ):
            from wx4.steps import normalize_step

            result = normalize_step(ctx)

        m_ext.assert_called_once()
        m_norm.assert_called_once()
        m_enc.assert_called_once()
        assert result.normalized is not None
        assert result.normalized.name.endswith("_normalized.m4a")

    def test_skips_on_cache_hit(self, tmp_path):
        norm = tmp_path / "audio_normalized.m4a"
        norm.write_bytes(b"normalized")
        ctx = _ctx(tmp_path, cache_hit=True, normalized=norm)

        with patch("wx4.steps.extract_to_wav") as m_ext:
            from wx4.steps import normalize_step

            result = normalize_step(ctx)

        m_ext.assert_not_called()
        assert result.normalized == norm

    def test_does_not_call_apply_clearvoice(self, tmp_path):
        ctx = _ctx(tmp_path, cache_hit=False, output_m4a=True)

        def fake_to_aac(src, dst, **kw):
            dst.write_bytes(b"aac")
            return True

        with (
            patch("wx4.steps.extract_to_wav", return_value=True),
            patch("wx4.steps.normalize_lufs"),
            patch("wx4.steps.to_aac", side_effect=fake_to_aac),
            patch("wx4.steps.apply_clearvoice") as m_cv,
        ):
            from wx4.steps import normalize_step

            normalize_step(ctx)

        m_cv.assert_not_called()

    def test_timing_recorded(self, tmp_path):
        ctx = _ctx(tmp_path, cache_hit=False, output_m4a=True)

        def fake_to_aac(src, dst, **kw):
            dst.write_bytes(b"aac")
            return True

        with (
            patch("wx4.steps.extract_to_wav", return_value=True),
            patch("wx4.steps.normalize_lufs"),
            patch("wx4.steps.to_aac", side_effect=fake_to_aac),
        ):
            from wx4.steps import normalize_step

            result = normalize_step(ctx)

        assert "normalize" in result.timings


# ---------------------------------------------------------------------------
# TestEnhanceStepAtomicity
# ---------------------------------------------------------------------------


class TestEnhanceStepAtomicity:
    def test_tmp_files_removed_after_success(self, tmp_path):
        """The 3 tmp files must NOT exist in the directory after a successful enhance."""
        ctx = _ctx(tmp_path, cache_hit=False, output_m4a=True)
        stem = ctx.src.stem

        def fake_to_aac(src, dst, **kw):
            dst.write_bytes(b"aac")
            return True

        with (
            patch("wx4.steps.extract_to_wav", return_value=True),
            patch("wx4.steps.normalize_lufs"),
            patch("wx4.steps.apply_clearvoice"),
            patch("wx4.steps.to_aac", side_effect=fake_to_aac),
            patch("wx4.steps._load_clearvoice", return_value=MagicMock()),
        ):
            from wx4.steps import enhance_step

            enhance_step(ctx)

        assert not (tmp_path / f"{stem}._tmp_raw.wav").exists()
        assert not (tmp_path / f"{stem}._tmp_norm.wav").exists()
        assert not (tmp_path / f"{stem}._tmp_enh.wav").exists()

    def test_cleanup_runs_even_if_encode_fails(self, tmp_path):
        """tmp_raw and tmp_norm must be cleaned up even if to_aac raises."""
        ctx = _ctx(tmp_path, cache_hit=False, output_m4a=True)
        stem = ctx.src.stem

        # Simulate tmp files being created by normalize/enhance before encode fails
        tmp_raw = tmp_path / f"{stem}._tmp_raw.wav"
        tmp_norm = tmp_path / f"{stem}._tmp_norm.wav"
        tmp_enh = tmp_path / f"{stem}._tmp_enh.wav"

        def fake_extract(src, dst, **kw):
            dst.write_bytes(b"raw")
            return True

        def fake_normalize(src, dst, **kw):
            dst.write_bytes(b"norm")

        def fake_enhance(src, dst, *args, **kw):
            dst.write_bytes(b"enh")

        with (
            patch("wx4.steps.extract_to_wav", side_effect=fake_extract),
            patch("wx4.steps.normalize_lufs", side_effect=fake_normalize),
            patch("wx4.steps.apply_clearvoice", side_effect=fake_enhance),
            patch("wx4.steps.to_aac", return_value=False),
            patch("wx4.steps._load_clearvoice", return_value=MagicMock()),
        ):
            from wx4.steps import enhance_step

            with pytest.raises(RuntimeError):
                enhance_step(ctx)

        assert not tmp_raw.exists()
        assert not tmp_norm.exists()
        assert not tmp_enh.exists()

    def test_final_output_not_written_when_encode_fails(self, tmp_path):
        """If to_aac fails, the final _enhanced.m4a must NOT exist."""
        ctx = _ctx(tmp_path, cache_hit=False, output_m4a=True)
        out = tmp_path / f"{ctx.src.stem}_enhanced.m4a"

        with (
            patch("wx4.steps.extract_to_wav", return_value=True),
            patch("wx4.steps.normalize_lufs"),
            patch("wx4.steps.apply_clearvoice"),
            patch("wx4.steps.to_aac", return_value=False),
            patch("wx4.steps._load_clearvoice", return_value=MagicMock()),
        ):
            from wx4.steps import enhance_step

            with pytest.raises(RuntimeError):
                enhance_step(ctx)

        assert not out.exists()


# ---------------------------------------------------------------------------
# TestTranscribeStep
# ---------------------------------------------------------------------------


class TestTranscribeStep:
    def test_uses_enhanced_path_when_set(self, tmp_path):
        enhanced = tmp_path / "audio_enhanced.m4a"
        ctx = _ctx(tmp_path, enhanced=enhanced)

        txt = tmp_path / "audio_enhanced_transcript.txt"
        jsn = tmp_path / "audio_enhanced_timestamps.json"
        txt.write_text("", encoding="utf-8")
        jsn.write_text("[]", encoding="utf-8")

        with patch(
            "wx4.steps.transcribe_assemblyai", return_value=(txt, jsn)
        ) as mock_t:
            from wx4.steps import transcribe_step

            transcribe_step(ctx)
        assert mock_t.call_args[0][0] == enhanced

    def test_uses_src_when_enhanced_is_none(self, tmp_path):
        ctx = _ctx(tmp_path, enhanced=None)

        txt = tmp_path / "audio_transcript.txt"
        jsn = tmp_path / "audio_timestamps.json"
        txt.write_text("", encoding="utf-8")
        jsn.write_text("[]", encoding="utf-8")

        with patch(
            "wx4.steps.transcribe_assemblyai", return_value=(txt, jsn)
        ) as mock_t:
            from wx4.steps import transcribe_step

            transcribe_step(ctx)
        assert mock_t.call_args[0][0] == ctx.src

    def test_sets_transcript_txt_and_json_on_ctx(self, tmp_path):
        ctx = _ctx(tmp_path)
        txt = tmp_path / "t.txt"
        jsn = tmp_path / "t.json"
        txt.write_text("", encoding="utf-8")
        jsn.write_text("[]", encoding="utf-8")

        with patch("wx4.steps.transcribe_assemblyai", return_value=(txt, jsn)):
            from wx4.steps import transcribe_step

            result = transcribe_step(ctx)
        assert result.transcript_txt == txt
        assert result.transcript_json == jsn

    def test_timing_recorded(self, tmp_path):
        ctx = _ctx(tmp_path)
        txt = tmp_path / "t.txt"
        jsn = tmp_path / "t.json"
        txt.write_text("", encoding="utf-8")
        jsn.write_text("[]", encoding="utf-8")

        with patch("wx4.steps.transcribe_assemblyai", return_value=(txt, jsn)):
            from wx4.steps import transcribe_step

            result = transcribe_step(ctx)
        assert "transcribe" in result.timings


# ---------------------------------------------------------------------------
# TestSrtStep
# ---------------------------------------------------------------------------


class TestSrtStep:
    def test_raises_when_transcript_json_is_none(self, tmp_path):
        ctx = _ctx(tmp_path, transcript_json=None)

        from wx4.steps import srt_step

        with pytest.raises(RuntimeError):
            srt_step(ctx)

    def test_reads_json_and_calls_words_to_srt(self, tmp_path):
        words = [{"text": "hi.", "start": 0, "end": 500, "speaker": "A"}]
        jsn = tmp_path / "audio_timestamps.json"
        jsn.write_text(json.dumps(words), encoding="utf-8")
        ctx = _ctx(tmp_path, transcript_json=jsn)

        with patch("wx4.steps.words_to_srt", return_value="1\n...") as mock_srt:
            from wx4.steps import srt_step

            srt_step(ctx)
        mock_srt.assert_called_once()

    def test_sets_srt_on_ctx(self, tmp_path):
        words = [{"text": "hi.", "start": 0, "end": 500, "speaker": "A"}]
        jsn = tmp_path / "audio_timestamps.json"
        jsn.write_text(json.dumps(words), encoding="utf-8")
        ctx = _ctx(tmp_path, transcript_json=jsn, srt_mode="speaker-only")

        from wx4.steps import srt_step

        result = srt_step(ctx)
        assert result.srt is not None
        assert result.srt.suffix == ".srt"

    def test_timing_recorded(self, tmp_path):
        words = [{"text": "hi.", "start": 0, "end": 500, "speaker": "A"}]
        jsn = tmp_path / "audio_timestamps.json"
        jsn.write_text(json.dumps(words), encoding="utf-8")
        ctx = _ctx(tmp_path, transcript_json=jsn)

        from wx4.steps import srt_step

        result = srt_step(ctx)
        assert "srt" in result.timings


# ---------------------------------------------------------------------------
# TestVideoStep
# ---------------------------------------------------------------------------


class TestVideoStep:
    def test_uses_enhanced_audio_when_available(self, tmp_path):
        enhanced = tmp_path / "audio_enhanced.m4a"
        ctx = _ctx(tmp_path, enhanced=enhanced)

        with patch("wx4.steps.audio_to_black_video", return_value=True) as mock_v:
            from wx4.steps import video_step

            video_step(ctx)
        assert mock_v.call_args[0][0] == enhanced

    def test_raises_when_audio_to_black_video_returns_false(self, tmp_path):
        ctx = _ctx(tmp_path)

        with patch("wx4.steps.audio_to_black_video", return_value=False):
            from wx4.steps import video_step

            with pytest.raises(RuntimeError):
                video_step(ctx)

    def test_sets_video_out_on_ctx(self, tmp_path):
        ctx = _ctx(tmp_path)

        with patch("wx4.steps.audio_to_black_video", return_value=True):
            from wx4.steps import video_step

            result = video_step(ctx)
        assert result.video_out is not None
        assert result.video_out.suffix == ".mp4"

    def test_video_out_stem_matches_srt_stem(self, tmp_path):
        """video_out and srt share the same stem for media player auto-pairing."""
        ctx = _ctx(tmp_path)

        with patch("wx4.steps.audio_to_black_video", return_value=True):
            from wx4.steps import video_step

            result = video_step(ctx)
        assert result.video_out.stem.endswith("_timestamps")

    def test_timing_recorded(self, tmp_path):
        ctx = _ctx(tmp_path)

        with patch("wx4.steps.audio_to_black_video", return_value=True):
            from wx4.steps import video_step

            result = video_step(ctx)
        assert "video" in result.timings

    def test_video_step_with_compress_uses_enhanced_audio(self, tmp_path):
        """When compress_ratio is set, video_step calls _compress_video with enhanced audio."""
        enhanced = tmp_path / "audio_enhanced.m4a"
        ctx = _ctx(tmp_path, enhanced=enhanced, compress_ratio=0.3)

        mock_info = MagicMock()
        mock_info.has_audio = True

        with (
            patch("wx4.steps.audio_to_black_video", return_value=True) as m_video,
            patch("wx4.steps._compress_video") as m_compress,
            patch("wx4.steps.probe_video", return_value=mock_info),
            patch("wx4.steps.measure_audio_lufs", return_value=-20.0),
            patch("wx4.steps.LufsInfo") as mock_lufs,
            patch("wx4.steps.detect_best_encoder", return_value=MagicMock()),
            patch("wx4.steps.calculate_video_bitrate") as m_bitrate,
        ):
            m_bitrate.return_value = 500_000
            mock_lufs.from_measured.return_value = MagicMock()
            mock_lufs.noop.return_value = MagicMock()

            from wx4.steps import video_step

            try:
                result = video_step(ctx)
            except FileNotFoundError:
                pass

        m_video.assert_called_once_with(enhanced, ANY)
        m_bitrate.assert_called_once_with(mock_info, 0.3)
        m_compress.assert_called_once()

    def test_video_step_compression_ratio_applied(self, tmp_path):
        """compress_ratio is passed to _compress_video via calculate_video_bitrate."""
        ctx = _ctx(tmp_path, compress_ratio=0.5)

        mock_info = MagicMock()
        mock_info.has_audio = True

        with (
            patch("wx4.steps.audio_to_black_video", return_value=True),
            patch("wx4.steps._compress_video") as m_compress,
            patch("wx4.steps.probe_video", return_value=mock_info),
            patch("wx4.steps.measure_audio_lufs", return_value=-20.0),
            patch("wx4.steps.LufsInfo") as mock_lufs,
            patch("wx4.steps.detect_best_encoder", return_value=MagicMock()),
            patch("wx4.steps.calculate_video_bitrate") as m_bitrate,
        ):
            m_bitrate.return_value = 500_000
            mock_lufs.from_measured.return_value = MagicMock()
            mock_lufs.noop.return_value = MagicMock()

            from wx4.steps import video_step

            try:
                video_step(ctx)
            except FileNotFoundError:
                pass

        m_bitrate.assert_called_once_with(mock_info, 0.5)
        m_compress.assert_called_once()

    def test_video_step_no_compress_when_ratio_none(self, tmp_path):
        """When compress_ratio is None, _compress_video is not called."""
        ctx = _ctx(tmp_path, compress_ratio=None)

        with (
            patch("wx4.steps.audio_to_black_video", return_value=True) as m_video,
            patch("wx4.steps._compress_video") as m_compress,
        ):
            from wx4.steps import video_step

            video_step(ctx)

        m_video.assert_called_once()
        m_compress.assert_not_called()


# ---------------------------------------------------------------------------
# TestCompressStep
# ---------------------------------------------------------------------------


def _compress_patches(info, lufs_instance=None):
    """Return a dict of patch targets -> mocks for compress_step dependencies."""
    if lufs_instance is None:
        lufs_instance = MagicMock()
    lufs_cls = MagicMock()
    lufs_cls.from_measured.return_value = lufs_instance
    lufs_cls.noop.return_value = lufs_instance
    return dict(
        probe_video=MagicMock(return_value=info),
        measure_audio_lufs=MagicMock(return_value=-20.0),
        LufsInfo=lufs_cls,
        detect_best_encoder=MagicMock(return_value=MagicMock()),
        calculate_video_bitrate=MagicMock(return_value=500_000),
        _compress_video=MagicMock(),
    )


def _video_info(has_audio=True):
    info = MagicMock()
    info.has_audio = has_audio
    info.duration_s = 60.0
    return info


class TestCompressStep:
    def test_calls_probe_video_with_src(self, tmp_path):
        ctx = _ctx(tmp_path, compress_ratio=0.40)
        patches = _compress_patches(_video_info())

        with patch.multiple("wx4.steps", **patches):
            from wx4.steps import compress_step

            compress_step(ctx)

        patches["probe_video"].assert_called_once_with(ctx.src)

    def test_skips_silently_when_source_has_no_video_stream(self, tmp_path):
        ctx = _ctx(tmp_path)

        with patch("wx4.steps.probe_video", side_effect=RuntimeError("no video stream")):
            from wx4.steps import compress_step

            result = compress_step(ctx)

        assert result.video_compressed is None

    def test_timing_recorded_on_audio_only_skip(self, tmp_path):
        ctx = _ctx(tmp_path)

        with patch("wx4.steps.probe_video", side_effect=RuntimeError("no video stream")):
            from wx4.steps import compress_step

            result = compress_step(ctx)

        assert "compress" in result.timings

    def test_measures_lufs_when_has_audio(self, tmp_path):
        ctx = _ctx(tmp_path)
        patches = _compress_patches(_video_info(has_audio=True))

        with patch.multiple("wx4.steps", **patches):
            from wx4.steps import compress_step

            compress_step(ctx)

        patches["measure_audio_lufs"].assert_called_once_with(ctx.src)

    def test_uses_lufs_noop_when_no_audio(self, tmp_path):
        ctx = _ctx(tmp_path)
        patches = _compress_patches(_video_info(has_audio=False))

        with patch.multiple("wx4.steps", **patches):
            from wx4.steps import compress_step

            compress_step(ctx)

        patches["measure_audio_lufs"].assert_not_called()
        patches["LufsInfo"].noop.assert_called_once()

    def test_calls_detect_encoder_with_compress_ratio(self, tmp_path):
        ctx = _ctx(tmp_path, compress_ratio=0.40)
        patches = _compress_patches(_video_info())

        with patch.multiple("wx4.steps", **patches):
            from wx4.steps import compress_step

            compress_step(ctx)

        patches["detect_best_encoder"].assert_called_once_with(force=None)

    def test_calls_calculate_bitrate_with_compress_ratio(self, tmp_path):
        ctx = _ctx(tmp_path, compress_ratio=0.30)
        info = _video_info()
        patches = _compress_patches(info)

        with patch.multiple("wx4.steps", **patches):
            from wx4.steps import compress_step

            compress_step(ctx)

        patches["calculate_video_bitrate"].assert_called_once_with(info, 0.30)

    def test_calls_compress_video(self, tmp_path):
        ctx = _ctx(tmp_path)
        patches = _compress_patches(_video_info())

        with patch.multiple("wx4.steps", **patches):
            from wx4.steps import compress_step

            compress_step(ctx)

        patches["_compress_video"].assert_called_once()

    def test_passes_step_progress_callback_to_compress_video(self, tmp_path):
        """compress_step should pass ctx.step_progress as progress_callback."""
        from wx4.steps import compress_step

        ctx = _ctx(tmp_path)
        ctx.step_progress = MagicMock()
        patches = _compress_patches(_video_info())

        with patch.multiple("wx4.steps", **patches):
            compress_step(ctx)

        call_kwargs = patches["_compress_video"].call_args.kwargs
        assert "progress_callback" in call_kwargs
        assert call_kwargs["progress_callback"] == ctx.step_progress

    def test_sets_video_compressed_on_ctx(self, tmp_path):
        ctx = _ctx(tmp_path)
        patches = _compress_patches(_video_info())

        with patch.multiple("wx4.steps", **patches):
            from wx4.steps import compress_step

            result = compress_step(ctx)

        assert result.video_compressed is not None

    def test_output_path_is_src_stem_compressed_mp4(self, tmp_path):
        ctx = _ctx(tmp_path)
        patches = _compress_patches(_video_info())

        with patch.multiple("wx4.steps", **patches):
            from wx4.steps import compress_step

            result = compress_step(ctx)

        expected = ctx.src.parent / f"{ctx.src.stem}_compressed.mp4"
        assert result.video_compressed == expected

    def test_timing_recorded(self, tmp_path):
        ctx = _ctx(tmp_path)
        patches = _compress_patches(_video_info())

        with patch.multiple("wx4.steps", **patches):
            from wx4.steps import compress_step

            result = compress_step(ctx)

        assert "compress" in result.timings


# ---------------------------------------------------------------------------
# TestEnhanceStepPassesStepProgress
# ---------------------------------------------------------------------------


class TestEnhanceStepPassesStepProgress:
    def test_step_progress_forwarded_to_apply_clearvoice(self, tmp_path):
        cb = MagicMock()
        ctx = _ctx(tmp_path, cache_hit=False, output_m4a=True, step_progress=cb)

        def fake_to_aac(src, dst, **kw):
            dst.write_bytes(b"aac")
            return True

        with (
            patch("wx4.steps.extract_to_wav", return_value=True),
            patch("wx4.steps.normalize_lufs"),
            patch("wx4.steps.apply_clearvoice") as m_enh,
            patch("wx4.steps.to_aac", side_effect=fake_to_aac),
            patch("wx4.steps._load_clearvoice", return_value=MagicMock()),
        ):
            from wx4.steps import enhance_step

            enhance_step(ctx)

        assert m_enh.call_args.kwargs.get("progress_callback") is cb

    def test_step_progress_none_when_not_set(self, tmp_path):
        ctx = _ctx(tmp_path, cache_hit=False, output_m4a=True)

        def fake_to_aac(src, dst, **kw):
            dst.write_bytes(b"aac")
            return True

        with (
            patch("wx4.steps.extract_to_wav", return_value=True),
            patch("wx4.steps.normalize_lufs"),
            patch("wx4.steps.apply_clearvoice") as m_enh,
            patch("wx4.steps.to_aac", side_effect=fake_to_aac),
            patch("wx4.steps._load_clearvoice", return_value=MagicMock()),
        ):
            from wx4.steps import enhance_step

            enhance_step(ctx)

        assert m_enh.call_args.kwargs.get("progress_callback") is None


# ---------------------------------------------------------------------------
# TestTranscribeStepBackendBranching
# ---------------------------------------------------------------------------


class TestTranscribeStepBackendBranching:
    def _make_files(self, tmp_path, stem):
        txt = tmp_path / f"{stem}_transcript.txt"
        jsn = tmp_path / f"{stem}_timestamps.json"
        txt.write_text("", encoding="utf-8")
        jsn.write_text("[]", encoding="utf-8")
        return txt, jsn

    def test_assemblyai_backend_calls_transcribe_assemblyai(self, tmp_path):
        ctx = _ctx(tmp_path, transcribe_backend="assemblyai")
        txt, jsn = self._make_files(tmp_path, "audio")
        with (
            patch(
                "wx4.steps.transcribe_assemblyai", return_value=(txt, jsn)
            ) as mock_aai,
            patch("wx4.steps.transcribe_with_whisper") as mock_wh,
        ):
            from wx4.steps import transcribe_step

            transcribe_step(ctx)
        mock_aai.assert_called_once()
        mock_wh.assert_not_called()

    def test_whisper_backend_calls_transcribe_with_whisper(self, tmp_path):
        ctx = _ctx(tmp_path, transcribe_backend="whisper", hf_token="hf_x")
        txt, jsn = self._make_files(tmp_path, "audio")
        with (
            patch(
                "wx4.steps.transcribe_with_whisper", return_value=(txt, jsn)
            ) as mock_wh,
            patch("wx4.steps.transcribe_assemblyai") as mock_aai,
        ):
            from wx4.steps import transcribe_step

            transcribe_step(ctx)
        mock_wh.assert_called_once()
        mock_aai.assert_not_called()

    def test_whisper_backend_forwards_hf_token(self, tmp_path):
        ctx = _ctx(tmp_path, transcribe_backend="whisper", hf_token="hf_secret")
        txt, jsn = self._make_files(tmp_path, "audio")
        with patch(
            "wx4.steps.transcribe_with_whisper", return_value=(txt, jsn)
        ) as mock_wh:
            from wx4.steps import transcribe_step

            transcribe_step(ctx)
        assert mock_wh.call_args.kwargs.get("hf_token") == "hf_secret"

    def test_whisper_backend_forwards_device(self, tmp_path):
        ctx = _ctx(tmp_path, transcribe_backend="whisper", hf_token="x", device="cpu")
        txt, jsn = self._make_files(tmp_path, "audio")
        with patch(
            "wx4.steps.transcribe_with_whisper", return_value=(txt, jsn)
        ) as mock_wh:
            from wx4.steps import transcribe_step

            transcribe_step(ctx)
        assert mock_wh.call_args.kwargs.get("device") == "cpu"

    def test_whisper_backend_forwards_whisper_model(self, tmp_path):
        ctx = _ctx(
            tmp_path,
            transcribe_backend="whisper",
            hf_token="x",
            whisper_model="openai/whisper-small",
        )
        txt, jsn = self._make_files(tmp_path, "audio")
        with patch(
            "wx4.steps.transcribe_with_whisper", return_value=(txt, jsn)
        ) as mock_wh:
            from wx4.steps import transcribe_step

            transcribe_step(ctx)
        assert mock_wh.call_args.kwargs.get("whisper_model") == "openai/whisper-small"

    def test_unknown_backend_raises_runtime_error(self, tmp_path):
        ctx = _ctx(tmp_path, transcribe_backend="unknown_backend")
        with pytest.raises(RuntimeError, match="unknown_backend"):
            from wx4.steps import transcribe_step

            transcribe_step(ctx)
