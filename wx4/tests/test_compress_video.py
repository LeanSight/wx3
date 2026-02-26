"""
Tests for wx4/compress_video.py - progress_callback parameter.
"""

from unittest.mock import MagicMock, patch
import pytest


class TestCompressVideoProgressCallback:
    """Tests for progress_callback parameter in compress_video()."""

    def test_calls_callback_when_provided(self, tmp_path):
        """compress_video should call progress_callback with (done, total) values."""
        from wx4.compress_video import compress_video, VideoInfo, LufsInfo, EncoderInfo

        info = MagicMock(spec=VideoInfo)
        info.duration_s = 10.0
        info.size_bytes = 1000
        info.has_audio = False

        lufs = LufsInfo.noop()
        encoder = EncoderInfo("libx264", "CPU", {})
        output = tmp_path / "output.mp4"

        callback = MagicMock()

        with patch("wx4.compress_video._build_encode_stream") as mock_build:
            mock_build.return_value = MagicMock()
            with patch("wx4.compress_video._run_with_progress") as mock_run:

                def capture_callback(*args, **kwargs):
                    cb = kwargs.get("progress_callback")
                    if cb:
                        cb(50, 100)
                        cb(100, 100)

                mock_run.side_effect = capture_callback

                compress_video(
                    info, lufs, encoder, 1000, output, progress_callback=callback
                )

        callback.assert_called()

    def test_no_progress_when_callback_none(self, tmp_path):
        """compress_video should not call callback when progress_callback is None."""
        from wx4.compress_video import compress_video, VideoInfo, LufsInfo, EncoderInfo

        info = MagicMock(spec=VideoInfo)
        info.duration_s = 10.0
        info.size_bytes = 1000
        info.has_audio = False

        lufs = LufsInfo.noop()
        encoder = EncoderInfo("libx264", "CPU", {})
        output = tmp_path / "output.mp4"

        with patch("wx4.compress_video._run_with_progress") as mock_run:
            with patch("wx4.compress_video._build_encode_stream"):
                compress_video(
                    info, lufs, encoder, 1000, output, progress_callback=None
                )

        mock_run.assert_called()
