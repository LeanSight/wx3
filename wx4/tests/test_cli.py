"""
Tests for wx4/cli.py - Typer CLI.
Uses typer.testing.CliRunner.
"""

import dataclasses
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def _make_ctx(tmp_path, **kwargs):
    from wx4.context import PipelineContext

    src = tmp_path / "audio.mp3"
    src.write_bytes(b"audio")
    return PipelineContext(src=src, srt=tmp_path / "audio.srt", **kwargs)


class TestCli:
    def test_unknown_file_prints_error(self, tmp_path):
        from typer.testing import CliRunner

        from wx4.cli import app

        runner = CliRunner()
        result = runner.invoke(app, [str(tmp_path / "nonexistent.wav")])
        assert "not found" in result.output.lower() or result.exit_code != 0

    def test_calls_pipeline_run_once_per_file(self, tmp_path):
        from typer.testing import CliRunner

        from wx4.cli import app

        f = tmp_path / "audio.mp3"
        f.write_bytes(b"audio")

        mock_ctx = _make_ctx(tmp_path)
        mock_pipeline = MagicMock()
        mock_pipeline.run.return_value = mock_ctx

        with patch("wx4.cli.Pipeline", return_value=mock_pipeline):
            runner = CliRunner()
            runner.invoke(app, [str(f)])

        mock_pipeline.run.assert_called_once()

    def test_skip_enhance_flag_forwarded(self, tmp_path):
        from typer.testing import CliRunner

        from wx4.cli import app

        f = tmp_path / "audio.mp3"
        f.write_bytes(b"audio")
        mock_ctx = _make_ctx(tmp_path)

        with patch("wx4.cli.Pipeline") as MockPipeline, patch(
            "wx4.cli.build_steps"
        ) as mock_build:
            MockPipeline.return_value.run.return_value = mock_ctx
            mock_build.return_value = []
            runner = CliRunner()
            runner.invoke(app, [str(f), "--skip-enhance"])

        call_kwargs = mock_build.call_args.kwargs
        assert call_kwargs.get("skip_enhance") is True

    def test_videooutput_flag_forwarded(self, tmp_path):
        from typer.testing import CliRunner

        from wx4.cli import app

        f = tmp_path / "audio.mp3"
        f.write_bytes(b"audio")
        mock_ctx = _make_ctx(tmp_path)

        with patch("wx4.cli.Pipeline") as MockPipeline, patch(
            "wx4.cli.build_steps"
        ) as mock_build:
            MockPipeline.return_value.run.return_value = mock_ctx
            mock_build.return_value = []
            runner = CliRunner()
            runner.invoke(app, [str(f), "--videooutput"])

        call_kwargs = mock_build.call_args.kwargs
        assert call_kwargs.get("videooutput") is True

    def test_force_flag_forwarded(self, tmp_path):
        from typer.testing import CliRunner

        from wx4.cli import app

        f = tmp_path / "audio.mp3"
        f.write_bytes(b"audio")
        mock_ctx = _make_ctx(tmp_path)

        with patch("wx4.cli.Pipeline") as MockPipeline, patch(
            "wx4.cli.build_steps"
        ) as mock_build:
            MockPipeline.return_value.run.return_value = mock_ctx
            mock_build.return_value = []
            runner = CliRunner()
            runner.invoke(app, [str(f), "--force"])

        call_kwargs = mock_build.call_args.kwargs
        assert call_kwargs.get("force") is True

    def test_speaker_names_parsed_and_forwarded(self, tmp_path):
        from typer.testing import CliRunner

        from wx4.cli import app

        f = tmp_path / "audio.mp3"
        f.write_bytes(b"audio")
        mock_ctx = _make_ctx(tmp_path)
        captured = {}

        def fake_run(ctx):
            captured["speaker_names"] = ctx.speaker_names
            return mock_ctx

        with patch("wx4.cli.Pipeline") as MockPipeline, patch(
            "wx4.cli.build_steps", return_value=[]
        ):
            MockPipeline.return_value.run.side_effect = fake_run
            runner = CliRunner()
            runner.invoke(app, [str(f), "--speakers-map", "A=Marcel,B=Agustin"])

        assert captured.get("speaker_names") == {"A": "Marcel", "B": "Agustin"}

    def test_no_args_shows_help(self):
        """python -m wx4.cli with no arguments must show help, not an error."""
        from typer.testing import CliRunner

        from wx4.cli import app

        runner = CliRunner()
        result = runner.invoke(app, [])
        assert result.exit_code == 0
        assert "--help" in result.output or "Usage" in result.output

    def test_output_contains_no_non_ascii(self, tmp_path):
        """Summary table output must be ASCII-only (Windows cp1252 compliance)."""
        from typer.testing import CliRunner

        from wx4.cli import app

        f = tmp_path / "audio.mp3"
        f.write_bytes(b"audio")
        mock_ctx = _make_ctx(tmp_path)

        with patch("wx4.cli.Pipeline") as MockPipeline, patch(
            "wx4.cli.build_steps", return_value=[]
        ):
            MockPipeline.return_value.run.return_value = mock_ctx
            runner = CliRunner()
            result = runner.invoke(app, [str(f)])

        assert result.output.isascii(), f"Non-ASCII chars in output: {result.output!r}"

    def test_summary_table_in_output(self, tmp_path):
        from typer.testing import CliRunner

        from wx4.cli import app

        f = tmp_path / "audio.mp3"
        f.write_bytes(b"audio")
        mock_ctx = _make_ctx(tmp_path)

        with patch("wx4.cli.Pipeline") as MockPipeline, patch(
            "wx4.cli.build_steps", return_value=[]
        ):
            MockPipeline.return_value.run.return_value = mock_ctx
            runner = CliRunner()
            result = runner.invoke(app, [str(f)])

        # Rich table renders column headers
        assert "audio.mp3" in result.output or "Summary" in result.output

    def test_clearvoice_loaded_when_not_skip_enhance(self, tmp_path):
        """When skip_enhance=False, ClearVoice must be instantiated and set in ctx.cv."""
        from typer.testing import CliRunner

        from wx4.cli import app

        f = tmp_path / "audio.mp3"
        f.write_bytes(b"audio")
        mock_ctx = _make_ctx(tmp_path)
        captured = {}

        def fake_run(ctx):
            captured["cv"] = ctx.cv
            return mock_ctx

        MockCV = MagicMock()
        mock_cv_instance = MagicMock()
        MockCV.return_value = mock_cv_instance

        with patch("wx4.cli.Pipeline") as MockPipeline, patch(
            "wx4.cli.build_steps", return_value=[]
        ), patch("wx4.cli.ClearVoice", MockCV):
            MockPipeline.return_value.run.side_effect = fake_run
            runner = CliRunner()
            runner.invoke(app, [str(f)])

        MockCV.assert_called_once()
        assert captured.get("cv") is mock_cv_instance

    def test_cv_is_none_when_skip_enhance(self, tmp_path):
        """When skip_enhance=True, ClearVoice must NOT be instantiated."""
        from typer.testing import CliRunner

        from wx4.cli import app

        f = tmp_path / "audio.mp3"
        f.write_bytes(b"audio")
        mock_ctx = _make_ctx(tmp_path)
        captured = {}

        def fake_run(ctx):
            captured["cv"] = ctx.cv
            return mock_ctx

        MockCV = MagicMock()

        with patch("wx4.cli.Pipeline") as MockPipeline, patch(
            "wx4.cli.build_steps", return_value=[]
        ), patch("wx4.cli.ClearVoice", MockCV):
            MockPipeline.return_value.run.side_effect = fake_run
            runner = CliRunner()
            runner.invoke(app, [str(f), "--skip-enhance"])

        MockCV.assert_not_called()
        assert captured.get("cv") is None
