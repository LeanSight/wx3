"""
Tests for wx4/steps.py - pipeline step functions.
All external calls are mocked via patch.
"""

import dataclasses
import json
from pathlib import Path
from unittest.mock import MagicMock, call, patch

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

        with patch("wx4.steps.save_cache") as mock_save, patch(
            "wx4.steps.file_key", return_value="fake-key"
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

        with patch("wx4.steps.save_cache"), patch(
            "wx4.steps.file_key", return_value="k"
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

    def test_calls_extract_normalize_enhance_encode_on_miss(self, tmp_path):
        ctx = _ctx(tmp_path, cache_hit=False, output_m4a=True, cv=MagicMock())

        with patch("wx4.steps.extract_to_wav", return_value=True) as m_ext, patch(
            "wx4.steps.normalize_lufs"
        ) as m_norm, patch("wx4.steps.apply_clearvoice") as m_enh, patch(
            "wx4.steps.to_aac", return_value=True
        ) as m_enc:
            from wx4.steps import enhance_step

            result = enhance_step(ctx)

        m_ext.assert_called_once()
        m_norm.assert_called_once()
        m_enh.assert_called_once()
        m_enc.assert_called_once()
        assert result.enhanced is not None

    def test_raises_when_extract_fails(self, tmp_path):
        ctx = _ctx(tmp_path, cache_hit=False, cv=MagicMock())

        with patch("wx4.steps.extract_to_wav", return_value=False):
            from wx4.steps import enhance_step

            with pytest.raises(RuntimeError):
                enhance_step(ctx)

    def test_raises_when_encode_fails(self, tmp_path):
        ctx = _ctx(tmp_path, cache_hit=False, output_m4a=True, cv=MagicMock())

        with patch("wx4.steps.extract_to_wav", return_value=True), patch(
            "wx4.steps.normalize_lufs"
        ), patch("wx4.steps.apply_clearvoice"), patch(
            "wx4.steps.to_aac", return_value=False
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

        with patch("wx4.steps.transcribe_assemblyai", return_value=(txt, jsn)) as mock_t:
            from wx4.steps import transcribe_step

            transcribe_step(ctx)
        assert mock_t.call_args[0][0] == enhanced

    def test_uses_src_when_enhanced_is_none(self, tmp_path):
        ctx = _ctx(tmp_path, enhanced=None)

        txt = tmp_path / "audio_transcript.txt"
        jsn = tmp_path / "audio_timestamps.json"
        txt.write_text("", encoding="utf-8")
        jsn.write_text("[]", encoding="utf-8")

        with patch("wx4.steps.transcribe_assemblyai", return_value=(txt, jsn)) as mock_t:
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

    def test_timing_recorded(self, tmp_path):
        ctx = _ctx(tmp_path)

        with patch("wx4.steps.audio_to_black_video", return_value=True):
            from wx4.steps import video_step

            result = video_step(ctx)
        assert "video" in result.timings
