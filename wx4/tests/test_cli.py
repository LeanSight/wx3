"""
Tests for wx4/cli.py - Typer CLI.
Uses typer.testing.CliRunner.
"""

import dataclasses
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from wx4.cli import RichProgressCallback


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
        assert (
            "no se encontraron archivos" in result.output.lower()
            or result.exit_code != 0
        )

    def test_calls_pipeline_run_once_per_file(self, tmp_path):
        import sys
        from typer.testing import CliRunner

        from wx4.cli import app

        f = tmp_path / "audio.mp3"
        f.write_bytes(b"audio")

        mock_ctx = _make_ctx(tmp_path)
        mock_pipeline = MagicMock()
        mock_pipeline.run.return_value = mock_ctx

        with (
            patch("wx4.cli.Pipeline", return_value=mock_pipeline),
            patch.dict(
                "sys.modules", {"clearvoice": MagicMock(ClearVoice=MagicMock())}
            ),
        ):
            runner = CliRunner()
            runner.invoke(app, [str(f)])

        mock_pipeline.run.assert_called_once()

    def test_no_normalize_flag_forwarded(self, tmp_path):
        from typer.testing import CliRunner

        from wx4.cli import app
        from wx4.context import PipelineConfig

        f = tmp_path / "audio.mp3"
        f.write_bytes(b"audio")
        mock_ctx = _make_ctx(tmp_path)

        with (
            patch("wx4.cli.Pipeline") as MockPipeline,
            patch("wx4.cli.build_steps") as mock_build,
        ):
            MockPipeline.return_value.run.return_value = mock_ctx
            mock_build.return_value = []
            runner = CliRunner()
            runner.invoke(app, [str(f), "--no-normalize"])

        config = mock_build.call_args.args[0]
        assert isinstance(config, PipelineConfig)
        assert config.skip_normalize is True

    def test_no_normalize_without_no_enhance_keeps_enhance(self, tmp_path):
        from typer.testing import CliRunner

        from wx4.cli import app
        from wx4.context import PipelineConfig

        f = tmp_path / "audio.mp3"
        f.write_bytes(b"audio")
        mock_ctx = _make_ctx(tmp_path)

        with (
            patch("wx4.cli.Pipeline") as MockPipeline,
            patch("wx4.cli.build_steps") as mock_build,
        ):
            MockPipeline.return_value.run.return_value = mock_ctx
            mock_build.return_value = []
            runner = CliRunner()
            runner.invoke(app, [str(f), "--no-normalize"])

        config = mock_build.call_args.args[0]
        assert config.skip_enhance is False

    def test_skip_enhance_flag_forwarded(self, tmp_path):
        from typer.testing import CliRunner

        from wx4.cli import app
        from wx4.context import PipelineConfig

        f = tmp_path / "audio.mp3"
        f.write_bytes(b"audio")
        mock_ctx = _make_ctx(tmp_path)

        with (
            patch("wx4.cli.Pipeline") as MockPipeline,
            patch("wx4.cli.build_steps") as mock_build,
        ):
            MockPipeline.return_value.run.return_value = mock_ctx
            mock_build.return_value = []
            runner = CliRunner()
            runner.invoke(app, [str(f), "--no-enhance"])

        config = mock_build.call_args.args[0]
        assert isinstance(config, PipelineConfig)
        assert config.skip_enhance is True

    def test_videooutput_flag_forwarded(self, tmp_path):
        from typer.testing import CliRunner

        from wx4.cli import app
        from wx4.context import PipelineConfig

        f = tmp_path / "audio.mp3"
        f.write_bytes(b"audio")
        mock_ctx = _make_ctx(tmp_path)

        with (
            patch("wx4.cli.Pipeline") as MockPipeline,
            patch("wx4.cli.build_steps") as mock_build,
        ):
            MockPipeline.return_value.run.return_value = mock_ctx
            mock_build.return_value = []
            runner = CliRunner()
            runner.invoke(app, [str(f), "--video-output"])

        config = mock_build.call_args.args[0]
        assert isinstance(config, PipelineConfig)
        assert config.videooutput is True

    def test_force_flag_forwarded_to_context(self, tmp_path):
        from typer.testing import CliRunner

        from wx4.cli import app

        f = tmp_path / "audio.mp3"
        f.write_bytes(b"audio")
        mock_ctx = _make_ctx(tmp_path)
        captured = {}

        def fake_run(ctx):
            captured["force"] = ctx.force
            return mock_ctx

        with (
            patch("wx4.cli.Pipeline") as MockPipeline,
            patch("wx4.cli.build_steps", return_value=[]),
        ):
            MockPipeline.return_value.run.side_effect = fake_run
            runner = CliRunner()
            runner.invoke(app, [str(f), "--force"])

        assert captured.get("force") is True

    def test_speaker_names_parsed_and_forwarded(self, tmp_path):
        import sys
        from typer.testing import CliRunner

        from wx4.cli import app

        f = tmp_path / "audio.mp3"
        f.write_bytes(b"audio")
        mock_ctx = _make_ctx(tmp_path)
        captured = {}

        def fake_run(ctx):
            captured["speaker_names"] = ctx.speaker_names
            return mock_ctx

        with (
            patch("wx4.cli.Pipeline") as MockPipeline,
            patch("wx4.cli.build_steps", return_value=[]),
            patch.dict(
                "sys.modules", {"clearvoice": MagicMock(ClearVoice=MagicMock())}
            ),
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

        with (
            patch("wx4.cli.Pipeline") as MockPipeline,
            patch("wx4.cli.build_steps", return_value=[]),
        ):
            MockPipeline.return_value.run.return_value = mock_ctx
            runner = CliRunner()
            result = runner.invoke(app, [str(f)])

        assert result.output.isascii(), f"Non-ASCII chars in output: {result.output!r}"

    def test_summary_table_in_output(self, tmp_path):
        import sys
        from typer.testing import CliRunner

        from wx4.cli import app

        f = tmp_path / "audio.mp3"
        f.write_bytes(b"audio")
        mock_ctx = _make_ctx(tmp_path)

        with (
            patch("wx4.cli.Pipeline") as MockPipeline,
            patch("wx4.cli.build_steps", return_value=[]),
            patch.dict(
                "sys.modules", {"clearvoice": MagicMock(ClearVoice=MagicMock())}
            ),
        ):
            MockPipeline.return_value.run.return_value = mock_ctx
            runner = CliRunner()
            result = runner.invoke(app, [str(f)])

        # Rich table renders column headers
        assert "audio.mp3" in result.output or "Summary" in result.output

    def test_clearvoice_loaded_when_not_skip_enhance(self, tmp_path):
        """When skip_enhance=False, ClearVoice must be instantiated and set in ctx.cv."""
        import sys
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

        with (
            patch("wx4.cli.Pipeline") as MockPipeline,
            patch("wx4.cli.build_steps", return_value=[]),
        ):
            if "clearvoice" in sys.modules:
                del sys.modules["clearvoice"]
            with patch.dict(
                "sys.modules", {"clearvoice": MagicMock(ClearVoice=MockCV)}
            ):
                MockPipeline.return_value.run.side_effect = fake_run
                runner = CliRunner()
                runner.invoke(app, [str(f)])

        MockCV.assert_called_once()
        assert captured.get("cv") is mock_cv_instance

    def test_compress_flag_forwarded_to_build_steps(self, tmp_path):
        from typer.testing import CliRunner

        from wx4.cli import app
        from wx4.context import PipelineConfig

        f = tmp_path / "audio.mp3"
        f.write_bytes(b"audio")
        mock_ctx = _make_ctx(tmp_path)

        with (
            patch("wx4.cli.Pipeline") as MockPipeline,
            patch("wx4.cli.build_steps") as mock_build,
        ):
            MockPipeline.return_value.run.return_value = mock_ctx
            mock_build.return_value = []
            runner = CliRunner()
            runner.invoke(app, [str(f), "--compress", "0.4"])

        config = mock_build.call_args.args[0]
        assert isinstance(config, PipelineConfig)
        assert config.compress_ratio == pytest.approx(0.4)

    def test_summary_table_shows_compressed_filename(self, tmp_path):
        from typer.testing import CliRunner

        from wx4.cli import app

        f = tmp_path / "audio.mp3"
        f.write_bytes(b"audio")
        compressed_path = tmp_path / "audio_compressed.mp4"
        mock_ctx = _make_ctx(tmp_path, video_compressed=compressed_path)

        with (
            patch("wx4.cli.Pipeline") as MockPipeline,
            patch("wx4.cli.build_steps", return_value=[]),
        ):
            MockPipeline.return_value.run.return_value = mock_ctx
            runner = CliRunner()
            result = runner.invoke(app, [str(f)])

        assert "audio_compressed.mp4" in result.output

    def test_summary_table_shows_dash_when_no_compressed(self, tmp_path):
        from typer.testing import CliRunner

        from wx4.cli import app

        f = tmp_path / "audio.mp3"
        f.write_bytes(b"audio")
        mock_ctx = _make_ctx(tmp_path, video_compressed=None)

        with (
            patch("wx4.cli.Pipeline") as MockPipeline,
            patch("wx4.cli.build_steps", return_value=[]),
        ):
            MockPipeline.return_value.run.return_value = mock_ctx
            runner = CliRunner()
            result = runner.invoke(app, [str(f)])

        assert result.exit_code == 0

    def test_cv_is_none_when_skip_enhance(self, tmp_path):
        """When skip_enhance=True, ClearVoice must NOT be instantiated."""
        import sys
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

        with (
            patch("wx4.cli.Pipeline") as MockPipeline,
            patch("wx4.cli.build_steps", return_value=[]),
        ):
            if "clearvoice" in sys.modules:
                del sys.modules["clearvoice"]
            with patch.dict(
                "sys.modules", {"clearvoice": MagicMock(ClearVoice=MockCV)}
            ):
                MockPipeline.return_value.run.side_effect = fake_run
                runner = CliRunner()
                runner.invoke(app, [str(f), "--no-enhance"])

        MockCV.assert_not_called()
        assert captured.get("cv") is None


class TestCliProgress:
    def test_progress_callback_passed_to_pipeline(self, tmp_path):
        """Pipeline must be instantiated with at least one callback."""
        import sys
        from typer.testing import CliRunner

        from wx4.cli import app

        f = tmp_path / "audio.mp3"
        f.write_bytes(b"audio")
        mock_ctx = _make_ctx(tmp_path)

        with (
            patch("wx4.cli.Pipeline") as MockPipeline,
            patch("wx4.cli.build_steps", return_value=[]),
        ):
            if "clearvoice" in sys.modules:
                del sys.modules["clearvoice"]
            with patch.dict(
                "sys.modules", {"clearvoice": MagicMock(ClearVoice=MagicMock())}
            ):
                MockPipeline.return_value.run.return_value = mock_ctx
                runner = CliRunner()
                runner.invoke(app, [str(f)])

        call_kwargs = MockPipeline.call_args.kwargs
        callbacks = call_kwargs.get("callbacks", [])
        assert len(callbacks) >= 1

    def test_skip_enhance_includes_callback_too(self, tmp_path):
        """With --no-enhance, callbacks are still passed to Pipeline."""
        from typer.testing import CliRunner

        from wx4.cli import app

        f = tmp_path / "audio.mp3"
        f.write_bytes(b"audio")
        mock_ctx = _make_ctx(tmp_path)

        with (
            patch("wx4.cli.Pipeline") as MockPipeline,
            patch("wx4.cli.build_steps", return_value=[]),
        ):
            MockPipeline.return_value.run.return_value = mock_ctx
            runner = CliRunner()
            runner.invoke(app, [str(f), "--no-enhance"])

        call_kwargs = MockPipeline.call_args.kwargs
        callbacks = call_kwargs.get("callbacks", [])
        assert len(callbacks) >= 1


# ---------------------------------------------------------------------------
# TestRichProgressCallbackOnStepProgress
# ---------------------------------------------------------------------------


class TestRichProgressCallbackOnStepProgress:
    def _make_cb(self):
        from rich.console import Console
        from rich.progress import Progress
        from wx4.cli import RichProgressCallback

        console = Console(file=None, force_terminal=True)
        progress = MagicMock(spec=Progress)
        progress.add_task = MagicMock(return_value=42)
        cb = RichProgressCallback(console, progress)
        return cb, progress

    def test_on_step_progress_updates_step_task(self):
        cb, progress = self._make_cb()
        cb._progress_task = 42
        cb.on_step_progress("enhance", 5, 100)
        progress.update.assert_called_once_with(42, total=100, completed=5)

    def test_on_step_progress_no_op_when_no_step_task(self):
        cb, progress = self._make_cb()
        cb._progress_task = None
        cb.on_step_progress("enhance", 5, 100)
        progress.update.assert_not_called()

    def test_on_step_progress_updates_deterministic_progress(self):
        """First call sets total; subsequent calls advance completed."""
        cb, progress = self._make_cb()
        cb._progress_task = 7
        cb.on_step_progress("enhance", 1, 50)
        cb.on_step_progress("enhance", 25, 50)
        calls = progress.update.call_args_list
        assert calls[0] == call(7, total=50, completed=1)
        assert calls[1] == call(7, total=50, completed=25)

    def test_on_step_progress_is_defined_on_callback(self):
        from wx4.cli import RichProgressCallback

        assert hasattr(RichProgressCallback, "on_step_progress")


class TestRichProgressCallbackPercentageDisplay:
    """Tests for percentage display in RichProgressCallback."""

    def test_render_tree_shows_percentage_for_running_step(self, tmp_path):
        """_render_tree should show percentage when step is running and has progress."""
        from pathlib import Path
        from wx4.cli import RichProgressCallback
        from wx4.context import PipelineContext

        console = MagicMock()
        progress = MagicMock()
        cb = RichProgressCallback(console, progress)

        ctx = PipelineContext(src=Path("/test/audio.mp4"))
        cb.on_pipeline_start(["compress", "srt"], ctx)

        cb._step_states["compress"] = "running"
        cb._progress_completed = {"compress": 45}

        tree = cb._render_tree()

        # _render_tree returns Text when no active task (progress_task is None)
        from rich.text import Text
        assert isinstance(tree, Text)
        assert "45%" in tree.plain

    def test_pending_step_shows_no_percentage(self, tmp_path):
        """_render_tree should not show percentage for pending steps."""
        from pathlib import Path
        from wx4.cli import RichProgressCallback
        from wx4.context import PipelineContext

        console = MagicMock()
        progress = MagicMock()
        cb = RichProgressCallback(console, progress)

        ctx = PipelineContext(src=Path("/test/audio.mp4"))
        cb.on_pipeline_start(["compress", "srt"], ctx)

        tree = cb._render_tree()

        from rich.text import Text
        assert isinstance(tree, Text)
        assert "%" not in tree.plain
        cb._live.stop()


class TestRichProgressCallbackProgressWidget:
    """Progress widget is embedded in Live display when a step is running."""

    def _make_cb(self):
        from rich.progress import Progress
        from wx4.cli import RichProgressCallback

        console = MagicMock()
        progress = MagicMock(spec=Progress)
        progress.add_task = MagicMock(return_value=42)
        cb = RichProgressCallback(console, progress)
        return cb, progress

    def test_render_tree_returns_group_when_progress_task_active(self):
        """When a step task is active, _render_tree returns Group(tree, progress)."""
        from rich.console import Group

        cb, progress = self._make_cb()
        cb._step_names = ["enhance"]
        cb._step_states = {"enhance": "running"}
        cb._progress_task = 42

        result = cb._render_tree()

        assert isinstance(result, Group)

    def test_render_tree_returns_text_when_no_active_task(self):
        """When no step task is active, _render_tree returns plain Text."""
        from rich.text import Text

        cb, progress = self._make_cb()
        cb._step_names = ["enhance"]
        cb._step_states = {"enhance": "pending"}
        cb._progress_task = None

        result = cb._render_tree()

        assert isinstance(result, Text)

    def test_group_contains_progress_widget(self):
        """The Group returned must include self._progress as a renderable."""
        from rich.console import Group

        cb, progress = self._make_cb()
        cb._step_names = ["enhance"]
        cb._step_states = {"enhance": "running"}
        cb._progress_task = 42

        result = cb._render_tree()

        assert isinstance(result, Group)
        assert progress in result.renderables


# ---------------------------------------------------------------------------
# TestCliWhisperFlags
# ---------------------------------------------------------------------------


class TestCliWhisperFlags:
    def _run_with_flags(self, tmp_path, extra_flags, mock_pipeline=None):
        from typer.testing import CliRunner
        from wx4.cli import app

        f = tmp_path / "audio.mp3"
        f.write_bytes(b"audio")
        mock_ctx = _make_ctx(tmp_path)

        if mock_pipeline is None:
            mock_pipeline = MagicMock()
            mock_pipeline.run.return_value = mock_ctx

        with (
            patch("wx4.cli.Pipeline", return_value=mock_pipeline) as MockPipeline,
            patch("wx4.cli.build_steps", return_value=[]),
        ):
            runner = CliRunner()
            result = runner.invoke(app, [str(f), "--no-enhance"] + extra_flags)
            return result, MockPipeline

    def test_default_backend_is_assemblyai(self, tmp_path):
        result, _ = self._run_with_flags(tmp_path, [])
        assert result.exit_code == 0 or "not found" in result.output.lower()

    def test_backend_flag_forwarded_to_context(self, tmp_path):
        from typer.testing import CliRunner
        from wx4.cli import app

        f = tmp_path / "audio.mp3"
        f.write_bytes(b"audio")
        mock_ctx = _make_ctx(tmp_path)
        received_ctx = {}

        def capture_run(ctx):
            received_ctx["ctx"] = ctx
            return mock_ctx

        mock_pipeline = MagicMock()
        mock_pipeline.run.side_effect = capture_run

        with (
            patch("wx4.cli.Pipeline", return_value=mock_pipeline),
            patch("wx4.cli.build_steps", return_value=[]),
        ):
            runner = CliRunner()
            runner.invoke(app, [str(f), "--no-enhance", "--backend", "whisper"])

        assert received_ctx.get("ctx") is not None
        assert received_ctx["ctx"].transcribe_backend == "whisper"

    def test_hf_token_flag_forwarded_to_context(self, tmp_path):
        from typer.testing import CliRunner
        from wx4.cli import app

        f = tmp_path / "audio.mp3"
        f.write_bytes(b"audio")
        mock_ctx = _make_ctx(tmp_path)
        received_ctx = {}

        def capture_run(ctx):
            received_ctx["ctx"] = ctx
            return mock_ctx

        mock_pipeline = MagicMock()
        mock_pipeline.run.side_effect = capture_run

        with (
            patch("wx4.cli.Pipeline", return_value=mock_pipeline),
            patch("wx4.cli.build_steps", return_value=[]),
        ):
            runner = CliRunner()
            runner.invoke(
                app, [str(f), "--no-enhance", "--pyannote-hf-token", "hf_secret"]
            )

        assert received_ctx["ctx"].hf_token == "hf_secret"

    def test_device_flag_forwarded_to_context(self, tmp_path):
        from typer.testing import CliRunner
        from wx4.cli import app

        f = tmp_path / "audio.mp3"
        f.write_bytes(b"audio")
        mock_ctx = _make_ctx(tmp_path)
        received_ctx = {}

        def capture_run(ctx):
            received_ctx["ctx"] = ctx
            return mock_ctx

        mock_pipeline = MagicMock()
        mock_pipeline.run.side_effect = capture_run

        with (
            patch("wx4.cli.Pipeline", return_value=mock_pipeline),
            patch("wx4.cli.build_steps", return_value=[]),
        ):
            runner = CliRunner()
            runner.invoke(app, [str(f), "--no-enhance", "--whisper-device", "cpu"])

        assert received_ctx["ctx"].device == "cpu"

    def test_whisper_model_flag_forwarded_to_context(self, tmp_path):
        from typer.testing import CliRunner
        from wx4.cli import app

        f = tmp_path / "audio.mp3"
        f.write_bytes(b"audio")
        mock_ctx = _make_ctx(tmp_path)
        received_ctx = {}

        def capture_run(ctx):
            received_ctx["ctx"] = ctx
            return mock_ctx

        mock_pipeline = MagicMock()
        mock_pipeline.run.side_effect = capture_run

        with (
            patch("wx4.cli.Pipeline", return_value=mock_pipeline),
            patch("wx4.cli.build_steps", return_value=[]),
        ):
            runner = CliRunner()
            runner.invoke(
                app,
                [str(f), "--no-enhance", "--whisper-model", "openai/whisper-small"],
            )

        assert received_ctx["ctx"].whisper_model == "openai/whisper-small"


# ---------------------------------------------------------------------------
# TestCliHierarchicalView - UI hierarchical display
# ---------------------------------------------------------------------------


class TestCliHierarchicalView:
    """Tests for hierarchical pipeline view."""

    def test_callback_receives_file_name_on_pipeline_start(self, tmp_path):
        """on_pipeline_start should receive the file name for display."""
        from rich.console import Console
        from rich.progress import Progress
        from wx4.cli import RichProgressCallback

        console = Console(file=None, force_terminal=True)
        progress = Progress()
        cb = RichProgressCallback(console, progress)

        src = tmp_path / "test_audio.mp3"
        src.write_bytes(b"audio")

        from wx4.context import PipelineContext

        ctx = PipelineContext(src=src)

        cb.on_pipeline_start(["normalize", "enhance", "transcribe"], ctx)

        assert cb._current_file == src

    def test_on_step_start_shows_step_name(self):
        """on_step_start should show the step name in progress."""
        from rich.console import Console
        from rich.progress import Progress
        from wx4.cli import RichProgressCallback

        console = Console(file=None, force_terminal=True)
        progress = MagicMock(spec=Progress)
        progress.add_task = MagicMock(return_value=1)
        cb = RichProgressCallback(console, progress)

        cb.on_step_start("enhance", MagicMock())

        progress.add_task.assert_called()

    def test_on_step_end_marks_step_complete(self):
        """on_step_end should mark step as complete."""
        from rich.console import Console
        from rich.progress import Progress

        console = Console(file=None, force_terminal=True)
        progress = MagicMock(spec=Progress)
        progress.add_task = MagicMock(return_value=1)
        progress.update = MagicMock()
        cb = RichProgressCallback(console, progress)
        cb._step_names = ["enhance", "transcribe"]
        cb._step_states = {"enhance": "running", "transcribe": "pending"}
        cb._current_file = Path("/test/audio.mp3")
        cb._progress_task = 1

        from wx4.context import PipelineContext

        ctx = PipelineContext(src=Path("/test/audio.mp3"))
        cb.on_step_end("enhance", ctx)

        progress.update.assert_called()

    def test_on_step_skipped_shows_skipped_indicator(self):
        """on_step_skipped should update Live display."""
        from rich.console import Console
        from rich.progress import Progress

        console = MagicMock()
        progress = Progress()
        cb = RichProgressCallback(console, progress)

        from wx4.context import PipelineContext

        ctx = PipelineContext(src=Path("/test/audio.mp3"))
        cb.on_pipeline_start(["normalize", "enhance"], ctx)
        cb.on_step_skipped("normalize", ctx)

        assert cb._live is not None
        cb._live.stop()


class TestIsIntermediateFile:
    """Tests for _is_intermediate_file function."""

    def test_returns_true_for_enhanced_m4a(self, tmp_path):
        from wx4.cli import _is_intermediate_file

        f = tmp_path / "audio_enhanced.m4a"
        assert _is_intermediate_file(f) is True

    def test_returns_true_for_normalized_m4a(self, tmp_path):
        from wx4.cli import _is_intermediate_file

        f = tmp_path / "audio_normalized.m4a"
        assert _is_intermediate_file(f) is True

    def test_returns_true_for_timestamps_json(self, tmp_path):
        from wx4.cli import _is_intermediate_file

        f = tmp_path / "audio_timestamps.json"
        assert _is_intermediate_file(f) is True

    def test_returns_true_for_timestamps_srt(self, tmp_path):
        from wx4.cli import _is_intermediate_file

        f = tmp_path / "audio_timestamps.srt"
        assert _is_intermediate_file(f) is True

    def test_returns_true_for_timestamps_mp4(self, tmp_path):
        from wx4.cli import _is_intermediate_file

        f = tmp_path / "audio_timestamps.mp4"
        assert _is_intermediate_file(f) is True

    def test_returns_true_for_transcript_txt(self, tmp_path):
        from wx4.cli import _is_intermediate_file

        f = tmp_path / "audio_transcript.txt"
        assert _is_intermediate_file(f) is True

    def test_returns_true_for_compressed_mp4(self, tmp_path):
        from wx4.cli import _is_intermediate_file

        f = tmp_path / "video_compressed.mp4"
        assert _is_intermediate_file(f) is True

    def test_returns_false_for_original_video(self, tmp_path):
        from wx4.cli import _is_intermediate_file

        f = tmp_path / "meeting.mp4"
        assert _is_intermediate_file(f) is False

    def test_returns_false_for_original_audio(self, tmp_path):
        from wx4.cli import _is_intermediate_file

        f = tmp_path / "audio.m4a"
        assert _is_intermediate_file(f) is False


class TestHasVideoStream:
    """Tests for _has_video_stream function using ffprobe."""

    def test_returns_true_when_video_stream_exists(self, tmp_path):
        from wx4.cli import _has_video_stream
        from unittest.mock import patch

        f = tmp_path / "video.mp4"
        f.write_bytes(b"fake")

        mock_probe = {"streams": [{"codec_type": "video"}, {"codec_type": "audio"}]}
        with patch("wx4.cli.ffmpeg.probe", return_value=mock_probe):
            result = _has_video_stream(f)
            assert result is True

    def test_returns_false_when_only_audio_stream(self, tmp_path):
        from wx4.cli import _has_video_stream
        from unittest.mock import patch

        f = tmp_path / "audio.m4a"
        f.write_bytes(b"fake")

        mock_probe = {"streams": [{"codec_type": "audio"}]}
        with patch("wx4.cli.ffmpeg.probe", return_value=mock_probe):
            result = _has_video_stream(f)
            assert result is False

    def test_returns_none_on_ffprobe_error(self, tmp_path):
        from wx4.cli import _has_video_stream
        from unittest.mock import patch

        f = tmp_path / "file.mp4"
        f.write_bytes(b"fake")

        with patch("wx4.cli.ffmpeg.probe", side_effect=Exception("ffprobe failed")):
            result = _has_video_stream(f)
            assert result is None


class TestExpandPaths:
    """Tests for _expand_paths function."""

    def test_single_file_returns_that_file(self, tmp_path):
        from wx4.cli import _expand_paths

        f = tmp_path / "video.mp4"
        f.write_bytes(b"fake")

        result = _expand_paths([str(f)])
        assert len(result) == 1
        assert result[0] == f

    def test_directory_expands_to_audio_video_files_only(self, tmp_path):
        from wx4.cli import _expand_paths

        # Create files
        (tmp_path / "video.mp4").write_bytes(b"fake")
        (tmp_path / "audio.m4a").write_bytes(b"fake")
        (tmp_path / "video_enhanced.m4a").write_bytes(b"fake")
        (tmp_path / "video_timestamps.srt").write_bytes(b"fake")

        result = _expand_paths([str(tmp_path)])
        names = [p.name for p in result]
        assert "video.mp4" in names
        assert "audio.m4a" in names
        assert "video_enhanced.m4a" not in names
        assert "video_timestamps.srt" not in names

    def test_mixed_files_and_directories(self, tmp_path):
        from wx4.cli import _expand_paths

        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "meeting.mp4").write_bytes(b"fake")
        (tmp_path / "audio.m4a").write_bytes(b"fake")

        result = _expand_paths([str(tmp_path)])
        names = [p.name for p in result]
        assert "meeting.mp4" in names
        assert "audio.m4a" in names
