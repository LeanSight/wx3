"""
Tests for wx4/audio_extract.py - extract_to_wav().
Mock target: wx4.audio_extract.ffmpeg
"""

from unittest.mock import MagicMock, patch


def _make_ffmpeg_mock(run_side_effect=None):
    """Return a fully wired ffmpeg mock."""
    mock = MagicMock()
    mock.Error = type("Error", (Exception,), {})
    out = MagicMock()
    mock.input.return_value.audio = MagicMock()
    mock.output.return_value = out
    if run_side_effect is not None:
        out.run.side_effect = run_side_effect
    else:
        out.run.return_value = (b"", b"")
    return mock


class TestExtractToWav:
    def test_returns_true_on_success(self, tmp_path):
        mock_ffmpeg = _make_ffmpeg_mock()
        with patch("wx4.audio_extract.ffmpeg", mock_ffmpeg), patch(
            "wx4.audio_extract._GPU", False
        ):
            from wx4.audio_extract import extract_to_wav

            assert extract_to_wav(tmp_path / "in.mp3", tmp_path / "out.wav") is True

    def test_returns_false_when_ffmpeg_raises_error(self, tmp_path):
        mock_ffmpeg = _make_ffmpeg_mock()
        mock_ffmpeg.output.return_value.run.side_effect = mock_ffmpeg.Error("fail")
        with patch("wx4.audio_extract.ffmpeg", mock_ffmpeg), patch(
            "wx4.audio_extract._GPU", False
        ):
            from wx4.audio_extract import extract_to_wav

            assert extract_to_wav(tmp_path / "in.mp3", tmp_path / "out.wav") is False

    def test_output_params_ar_48000_ac_1_acodec_pcm_s16le(self, tmp_path):
        mock_ffmpeg = _make_ffmpeg_mock()
        with patch("wx4.audio_extract.ffmpeg", mock_ffmpeg), patch(
            "wx4.audio_extract._GPU", False
        ):
            from wx4.audio_extract import extract_to_wav

            extract_to_wav(tmp_path / "in.mp3", tmp_path / "out.wav")

        kw = mock_ffmpeg.output.call_args.kwargs
        assert kw["acodec"] == "pcm_s16le"
        assert kw["ar"] == 48000
        assert kw["ac"] == 1

    def test_cpu_path_when_no_gpu(self, tmp_path):
        mock_ffmpeg = _make_ffmpeg_mock()
        with patch("wx4.audio_extract.ffmpeg", mock_ffmpeg), patch(
            "wx4.audio_extract._GPU", False
        ):
            from wx4.audio_extract import extract_to_wav

            extract_to_wav(tmp_path / "in.mp3", tmp_path / "out.wav")

        # CPU path: ffmpeg.input called without hwaccel
        call_kwargs = mock_ffmpeg.input.call_args.kwargs
        assert "hwaccel" not in call_kwargs

    def test_gpu_path_when_gpu_available(self, tmp_path):
        mock_ffmpeg = _make_ffmpeg_mock()
        with patch("wx4.audio_extract.ffmpeg", mock_ffmpeg), patch(
            "wx4.audio_extract._GPU", True
        ):
            from wx4.audio_extract import extract_to_wav

            result = extract_to_wav(tmp_path / "in.mp3", tmp_path / "out.wav")

        assert result is True
        call_kwargs = mock_ffmpeg.input.call_args.kwargs
        assert call_kwargs.get("hwaccel") == "cuda"

    def test_fallback_to_cpu_when_gpu_fails(self, tmp_path):
        mock_ffmpeg = _make_ffmpeg_mock()
        # First call (GPU) raises, second call (CPU) succeeds
        out = mock_ffmpeg.output.return_value
        out.run.side_effect = [mock_ffmpeg.Error("gpu fail"), (b"", b"")]

        with patch("wx4.audio_extract.ffmpeg", mock_ffmpeg), patch(
            "wx4.audio_extract._GPU", True
        ):
            from wx4.audio_extract import extract_to_wav

            result = extract_to_wav(tmp_path / "in.mp3", tmp_path / "out.wav")

        assert result is True
        assert mock_ffmpeg.input.call_count == 2
