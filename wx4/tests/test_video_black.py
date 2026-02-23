"""
Tests for wx4/video_black.py - audio_to_black_video().
Mock target: wx4.video_black.ffmpeg
"""

from unittest.mock import MagicMock, patch


def _ffmpeg_mock(run_side_effect=None):
    mock = MagicMock()
    mock.Error = type("Error", (Exception,), {})
    out = MagicMock()
    mock.output.return_value = out
    if run_side_effect is not None:
        out.run.side_effect = run_side_effect
    else:
        out.run.return_value = (b"", b"")
    return mock


class TestAudioToBlackVideo:
    def test_returns_true_on_success(self, tmp_path):
        mock_ffmpeg = _ffmpeg_mock()
        with patch("wx4.video_black.ffmpeg", mock_ffmpeg), patch(
            "wx4.video_black._GPU", False
        ):
            from wx4.video_black import audio_to_black_video

            assert (
                audio_to_black_video(tmp_path / "in.m4a", tmp_path / "out.mp4") is True
            )

    def test_returns_false_on_ffmpeg_error(self, tmp_path):
        mock_ffmpeg = _ffmpeg_mock()
        mock_ffmpeg.output.return_value.run.side_effect = mock_ffmpeg.Error("fail")
        with patch("wx4.video_black.ffmpeg", mock_ffmpeg), patch(
            "wx4.video_black._GPU", False
        ):
            from wx4.video_black import audio_to_black_video

            assert (
                audio_to_black_video(tmp_path / "in.m4a", tmp_path / "out.mp4")
                is False
            )

    def test_wav_reencoded_to_aac(self, tmp_path):
        mock_ffmpeg = _ffmpeg_mock()
        with patch("wx4.video_black.ffmpeg", mock_ffmpeg), patch(
            "wx4.video_black._GPU", False
        ):
            from wx4.video_black import audio_to_black_video

            audio_to_black_video(tmp_path / "audio.wav", tmp_path / "out.mp4")

        kw = mock_ffmpeg.output.call_args.kwargs
        assert kw["acodec"] == "aac"

    def test_non_wav_stream_copied(self, tmp_path):
        mock_ffmpeg = _ffmpeg_mock()
        with patch("wx4.video_black.ffmpeg", mock_ffmpeg), patch(
            "wx4.video_black._GPU", False
        ):
            from wx4.video_black import audio_to_black_video

            audio_to_black_video(tmp_path / "audio.m4a", tmp_path / "out.mp4")

        kw = mock_ffmpeg.output.call_args.kwargs
        assert kw["acodec"] == "copy"

    def test_gpu_encoder_when_available(self, tmp_path):
        mock_ffmpeg = _ffmpeg_mock()
        with patch("wx4.video_black.ffmpeg", mock_ffmpeg), patch(
            "wx4.video_black._GPU", True
        ):
            from wx4.video_black import audio_to_black_video

            audio_to_black_video(tmp_path / "audio.m4a", tmp_path / "out.mp4")

        kw = mock_ffmpeg.output.call_args.kwargs
        assert kw["vcodec"] == "h264_nvenc"

    def test_cpu_encoder_when_no_gpu(self, tmp_path):
        mock_ffmpeg = _ffmpeg_mock()
        with patch("wx4.video_black.ffmpeg", mock_ffmpeg), patch(
            "wx4.video_black._GPU", False
        ):
            from wx4.video_black import audio_to_black_video

            audio_to_black_video(tmp_path / "audio.m4a", tmp_path / "out.mp4")

        kw = mock_ffmpeg.output.call_args.kwargs
        assert kw["vcodec"] == "libx264"
