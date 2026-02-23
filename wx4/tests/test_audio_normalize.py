"""
Tests for wx4/audio_normalize.py - measure_lufs() and normalize_lufs().
Mock targets: wx4.audio_normalize.ffmpeg, wx4.audio_normalize.shutil
"""

from unittest.mock import MagicMock, call, patch


def _ffmpeg_mock_with_stderr(stderr: bytes):
    mock = MagicMock()
    mock.Error = type("Error", (Exception,), {})
    mock.input.return_value.output.return_value.run.return_value = (b"", stderr)
    return mock


class TestMeasureLufs:
    def test_returns_parsed_lufs_value(self, tmp_path):
        stderr = b'"input_i" : "-23.5"'
        mock_ffmpeg = _ffmpeg_mock_with_stderr(stderr)
        with patch("wx4.audio_normalize.ffmpeg", mock_ffmpeg):
            from wx4.audio_normalize import measure_lufs

            assert measure_lufs(tmp_path / "test.wav") == -23.5

    def test_returns_minus_70_on_ffmpeg_error(self, tmp_path):
        mock_ffmpeg = MagicMock()
        mock_ffmpeg.Error = type("Error", (Exception,), {})
        mock_ffmpeg.input.return_value.output.return_value.run.side_effect = (
            mock_ffmpeg.Error("fail")
        )
        with patch("wx4.audio_normalize.ffmpeg", mock_ffmpeg):
            from wx4.audio_normalize import measure_lufs

            assert measure_lufs(tmp_path / "test.wav") == -70.0

    def test_returns_minus_70_on_negative_inf_stderr(self, tmp_path):
        stderr = b'"input_i" : "-inf"'
        mock_ffmpeg = _ffmpeg_mock_with_stderr(stderr)
        with patch("wx4.audio_normalize.ffmpeg", mock_ffmpeg):
            from wx4.audio_normalize import measure_lufs

            assert measure_lufs(tmp_path / "test.wav") == -70.0

    def test_returns_minus_70_on_value_error(self, tmp_path):
        stderr = b'"input_i" : "NaN"'
        mock_ffmpeg = _ffmpeg_mock_with_stderr(stderr)
        with patch("wx4.audio_normalize.ffmpeg", mock_ffmpeg):
            from wx4.audio_normalize import measure_lufs

            assert measure_lufs(tmp_path / "test.wav") == -70.0


class TestNormalizeLufs:
    def test_copies_when_silent(self, tmp_path):
        src = tmp_path / "src.wav"
        dst = tmp_path / "dst.wav"
        with patch("wx4.audio_normalize.measure_lufs", return_value=-70.0), patch(
            "wx4.audio_normalize.shutil"
        ) as mock_shutil:
            from wx4.audio_normalize import normalize_lufs

            normalize_lufs(src, dst)
        mock_shutil.copy2.assert_called_once_with(src, dst)

    def test_applies_correct_gain_formula(self, tmp_path):
        src = tmp_path / "src.wav"
        dst = tmp_path / "dst.wav"
        mock_ffmpeg = MagicMock()
        mock_ffmpeg.Error = type("Error", (Exception,), {})
        # current = -30, target = -23 -> gain = 7
        with patch("wx4.audio_normalize.measure_lufs", return_value=-30.0), patch(
            "wx4.audio_normalize.ffmpeg", mock_ffmpeg
        ):
            from wx4.audio_normalize import normalize_lufs

            normalize_lufs(src, dst)
        kw = mock_ffmpeg.input.return_value.output.call_args.kwargs
        assert "7.00dB" in kw["af"]

    def test_clamps_gain_above_plus_30(self, tmp_path):
        src = tmp_path / "src.wav"
        dst = tmp_path / "dst.wav"
        mock_ffmpeg = MagicMock()
        mock_ffmpeg.Error = type("Error", (Exception,), {})
        # current = -60, target = -23 -> raw gain = 37, clamped to 30
        with patch("wx4.audio_normalize.measure_lufs", return_value=-60.0), patch(
            "wx4.audio_normalize.ffmpeg", mock_ffmpeg
        ):
            from wx4.audio_normalize import normalize_lufs

            normalize_lufs(src, dst)
        kw = mock_ffmpeg.input.return_value.output.call_args.kwargs
        assert "30.00dB" in kw["af"]

    def test_clamps_gain_below_minus_30(self, tmp_path):
        src = tmp_path / "src.wav"
        dst = tmp_path / "dst.wav"
        mock_ffmpeg = MagicMock()
        mock_ffmpeg.Error = type("Error", (Exception,), {})
        # current = 10, target = -23 -> raw gain = -33, clamped to -30
        with patch("wx4.audio_normalize.measure_lufs", return_value=10.0), patch(
            "wx4.audio_normalize.ffmpeg", mock_ffmpeg
        ):
            from wx4.audio_normalize import normalize_lufs

            normalize_lufs(src, dst)
        kw = mock_ffmpeg.input.return_value.output.call_args.kwargs
        assert "-30.00dB" in kw["af"]

    def test_fallback_copy_on_ffmpeg_error(self, tmp_path):
        src = tmp_path / "src.wav"
        dst = tmp_path / "dst.wav"
        mock_ffmpeg = MagicMock()
        mock_ffmpeg.Error = type("Error", (Exception,), {})
        mock_ffmpeg.input.return_value.output.return_value.run.side_effect = (
            mock_ffmpeg.Error("fail")
        )
        with patch("wx4.audio_normalize.measure_lufs", return_value=-30.0), patch(
            "wx4.audio_normalize.ffmpeg", mock_ffmpeg
        ), patch("wx4.audio_normalize.shutil") as mock_shutil:
            from wx4.audio_normalize import normalize_lufs

            normalize_lufs(src, dst)
        mock_shutil.copy2.assert_called_once_with(src, dst)

    def test_always_returns_true(self, tmp_path):
        src = tmp_path / "src.wav"
        dst = tmp_path / "dst.wav"
        with patch("wx4.audio_normalize.measure_lufs", return_value=-30.0), patch(
            "wx4.audio_normalize.ffmpeg"
        ) as mock_ffmpeg:
            mock_ffmpeg.Error = type("Error", (Exception,), {})
            from wx4.audio_normalize import normalize_lufs

            assert normalize_lufs(src, dst) is True
