"""
Tests for wx4/video_merge.py - merge_video_audio().
Mock target: wx4.video_merge.ffmpeg
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


class TestMergeVideoAudio:
    def test_returns_true_on_success(self, tmp_path):
        mock_ffmpeg = _ffmpeg_mock()
        with patch("wx4.video_merge.ffmpeg", mock_ffmpeg):
            from wx4.video_merge import merge_video_audio

            assert (
                merge_video_audio(
                    tmp_path / "video.mp4",
                    tmp_path / "audio.m4a",
                    tmp_path / "out.mp4",
                )
                is True
            )

    def test_returns_false_on_ffmpeg_error(self, tmp_path):
        mock_ffmpeg = _ffmpeg_mock()
        mock_ffmpeg.output.return_value.run.side_effect = mock_ffmpeg.Error("fail")
        with patch("wx4.video_merge.ffmpeg", mock_ffmpeg):
            from wx4.video_merge import merge_video_audio

            assert (
                merge_video_audio(
                    tmp_path / "video.mp4",
                    tmp_path / "audio.m4a",
                    tmp_path / "out.mp4",
                )
                is False
            )

    def test_video_codec_is_copy(self, tmp_path):
        mock_ffmpeg = _ffmpeg_mock()
        with patch("wx4.video_merge.ffmpeg", mock_ffmpeg):
            from wx4.video_merge import merge_video_audio

            merge_video_audio(
                tmp_path / "video.mp4",
                tmp_path / "audio.m4a",
                tmp_path / "out.mp4",
            )
        kw = mock_ffmpeg.output.call_args.kwargs
        assert kw["vcodec"] == "copy"

    def test_audio_codec_is_copy(self, tmp_path):
        mock_ffmpeg = _ffmpeg_mock()
        with patch("wx4.video_merge.ffmpeg", mock_ffmpeg):
            from wx4.video_merge import merge_video_audio

            merge_video_audio(
                tmp_path / "video.mp4",
                tmp_path / "audio.m4a",
                tmp_path / "out.mp4",
            )
        kw = mock_ffmpeg.output.call_args.kwargs
        assert kw["acodec"] == "copy"
