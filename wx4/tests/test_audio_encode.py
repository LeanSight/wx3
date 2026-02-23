"""
Tests for wx4/audio_encode.py - to_aac().
Mock target: wx4.audio_encode.ffmpeg
"""

from unittest.mock import MagicMock, patch


def _ffmpeg_mock(run_side_effect=None):
    mock = MagicMock()
    mock.Error = type("Error", (Exception,), {})
    out = mock.input.return_value.output.return_value
    if run_side_effect is not None:
        out.run.side_effect = run_side_effect
    else:
        out.run.return_value = (b"", b"")
    return mock


class TestToAac:
    def test_returns_true_on_success(self, tmp_path):
        mock_ffmpeg = _ffmpeg_mock()
        with patch("wx4.audio_encode.ffmpeg", mock_ffmpeg):
            from wx4.audio_encode import to_aac

            assert to_aac(tmp_path / "in.wav", tmp_path / "out.m4a") is True

    def test_returns_false_on_ffmpeg_error(self, tmp_path):
        mock_ffmpeg = _ffmpeg_mock()
        mock_ffmpeg.input.return_value.output.return_value.run.side_effect = (
            mock_ffmpeg.Error("fail")
        )
        with patch("wx4.audio_encode.ffmpeg", mock_ffmpeg):
            from wx4.audio_encode import to_aac

            assert to_aac(tmp_path / "in.wav", tmp_path / "out.m4a") is False

    def test_uses_aac_codec(self, tmp_path):
        mock_ffmpeg = _ffmpeg_mock()
        with patch("wx4.audio_encode.ffmpeg", mock_ffmpeg):
            from wx4.audio_encode import to_aac

            to_aac(tmp_path / "in.wav", tmp_path / "out.m4a")
        kw = mock_ffmpeg.input.return_value.output.call_args.kwargs
        assert kw["acodec"] == "aac"

    def test_default_bitrate_192k(self, tmp_path):
        mock_ffmpeg = _ffmpeg_mock()
        with patch("wx4.audio_encode.ffmpeg", mock_ffmpeg):
            from wx4.audio_encode import to_aac

            to_aac(tmp_path / "in.wav", tmp_path / "out.m4a")
        kw = mock_ffmpeg.input.return_value.output.call_args.kwargs
        assert kw["audio_bitrate"] == "192k"

    def test_custom_bitrate_passed_to_ffmpeg(self, tmp_path):
        mock_ffmpeg = _ffmpeg_mock()
        with patch("wx4.audio_encode.ffmpeg", mock_ffmpeg):
            from wx4.audio_encode import to_aac

            to_aac(tmp_path / "in.wav", tmp_path / "out.m4a", bitrate="128k")
        kw = mock_ffmpeg.input.return_value.output.call_args.kwargs
        assert kw["audio_bitrate"] == "128k"
