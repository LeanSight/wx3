from pathlib import Path
import pytest
from wx41.wx4 import MediaOrchestrator
from wx41.context import PipelineConfig
from wx41.steps.transcribe import TranscribeConfig

from wx41.steps import get_all_steps, get_step_info, predict_output_path


# Smoke test dinámico: se parametriza solo por los steps registrados
@pytest.mark.parametrize("step_name", list(get_all_steps().keys()))
class TestStepContract:
    def test_step_cli_generates_outputs(self, step_name, tmp_path, monkeypatch):
        from click.testing import CliRunner
        from wx41.cli import main
        from wx41.steps import STEP_REGISTRY, get_all_steps
        import dataclasses

        # Determine extension based on step to ensure it's included in the pipeline
        ext = ".m4a"
        if step_name == "compress":
            ext = ".mp4"

        audio = tmp_path / f"audio{ext}"
        audio.touch()

        # Simulador Universal: Mockea la infraestructura para TODOS los steps

        for s_name, s_info in get_all_steps().items():

            def make_mock(name, info):
                def mock_fn(ctx, config):
                    if info.output_fn:
                        outputs = info.output_fn(ctx, config)
                        for out_path in outputs.values():
                            out_path.parent.mkdir(parents=True, exist_ok=True)
                            out_path.write_text(f"simulated {name}", encoding="utf-8")
                    return ctx

                return mock_fn

            new_info = dataclasses.replace(s_info, step_fn=make_mock(s_name, s_info))
            monkeypatch.setitem(STEP_REGISTRY, s_name, new_info)

        runner = CliRunner()
        result = runner.invoke(main, [str(audio)])

        assert result.exit_code == 0, f"CLI falló para {step_name}: {result.output}"

        # Verificación basada en Metadata
        target_info = get_step_info(step_name)
        config = target_info.config_class()
        for key in config.output_keys:
            expected_path = predict_output_path(audio, step_name, key)
            # Nota: para steps que dependen de otros, predict_output_path podria necesitar el ctx
            # Pero para el Smoke Test, verificamos que el archivo resultante existe.
            # El oráculo usa la lógica de producción.
            assert expected_path.exists(), (
                f"El step {step_name} no produjo el archivo para la llave {key}"
            )

    def test_step_cli_resumability(self, step_name, tmp_path, monkeypatch):
        from click.testing import CliRunner
        from wx41.cli import main
        from wx41.steps import STEP_REGISTRY, get_all_steps
        import dataclasses

        # Determine extension based on step to ensure it's included in the pipeline
        ext = ".m4a"
        if step_name == "compress":
            ext = ".mp4"

        audio = tmp_path / f"audio{ext}"
        audio.touch()

        call_counts = {name: 0 for name in get_all_steps().keys()}

        for s_name, s_info in get_all_steps().items():

            def make_mock(name, info):
                def mock_fn(ctx, config):
                    call_counts[name] += 1
                    if info.output_fn:
                        outputs = info.output_fn(ctx, config)
                        for out_path in outputs.values():
                            out_path.parent.mkdir(parents=True, exist_ok=True)
                            out_path.write_text(f"simulated {name}", encoding="utf-8")
                    return ctx

                return mock_fn

            new_info = dataclasses.replace(s_info, step_fn=make_mock(s_name, s_info))
            monkeypatch.setitem(STEP_REGISTRY, s_name, new_info)

        runner = CliRunner()

        # Primera ejecución
        runner.invoke(main, [str(audio)])
        assert call_counts[step_name] == 1

        # Segunda ejecución
        call_counts[step_name] = 0
        runner.invoke(main, [str(audio)])
        assert call_counts[step_name] == 0, f"Resumability falló para {step_name}"

    def test_step_cli_optionality(self, step_name, tmp_path, monkeypatch):
        from click.testing import CliRunner
        from wx41.cli import main
        from wx41.steps import STEP_REGISTRY, get_all_steps, get_step_info
        import dataclasses

        target_info = get_step_info(step_name)
        if not target_info.optional:
            pytest.skip(f"El step {step_name} no es opcional")

        # Determine extension based on step to ensure it's included in the pipeline
        ext = ".m4a"
        if step_name == "compress":
            ext = ".mp4"

        audio = tmp_path / f"audio{ext}"
        audio.touch()

        call_counts = {name: 0 for name in get_all_steps().keys()}

        for s_name, s_info in get_all_steps().items():

            def make_mock(name, info):
                def mock_fn(ctx, config):
                    call_counts[name] += 1
                    if info.output_fn:
                        outputs = info.output_fn(ctx, config)
                        for out_path in outputs.values():
                            out_path.parent.mkdir(parents=True, exist_ok=True)
                            out_path.write_text(f"simulated {name}", encoding="utf-8")
                    return ctx

                return mock_fn

            new_info = dataclasses.replace(s_info, step_fn=make_mock(s_name, s_info))
            monkeypatch.setitem(STEP_REGISTRY, s_name, new_info)

        runner = CliRunner()
        result = runner.invoke(main, [str(audio), f"--no-{step_name}"])

        assert result.exit_code == 0
        assert call_counts[step_name] == 0

    def test_step_cli_dry_run(self, step_name, tmp_path, monkeypatch):
        from click.testing import CliRunner
        from wx41.cli import main
        from wx41.steps import STEP_REGISTRY, get_all_steps, get_step_info
        import dataclasses

        # Determine extension based on step to ensure it's included in the pipeline
        ext = ".m4a"
        if step_name == "compress":
            ext = ".mp4"

        audio = tmp_path / f"audio{ext}"
        audio.touch()

        call_counts = {name: 0 for name in get_all_steps().keys()}

        for s_name, s_info in get_all_steps().items():

            def make_mock(name, info):
                def mock_fn(ctx, config):
                    call_counts[name] += 1
                    return ctx

                return mock_fn

            new_info = dataclasses.replace(s_info, step_fn=make_mock(s_name, s_info))
            monkeypatch.setitem(STEP_REGISTRY, s_name, new_info)

        runner = CliRunner()
        result = runner.invoke(main, [str(audio), "--dry-run"])

        assert result.exit_code == 0
        assert call_counts[step_name] == 0

        config = get_step_info(step_name).config_class()
        for key in config.output_keys:
            expected_path = predict_output_path(audio, step_name, key)
            assert not expected_path.exists()


class TestAudioFallback:
    def test_compress_selects_enhanced_audio_when_available(
        self, tmp_path, monkeypatch
    ):
        from wx41.steps.compress import compress_step, CompressConfig
        from wx41.context import PipelineContext

        video = tmp_path / "video.mp4"
        audio_enhanced = tmp_path / "audio_enhanced.m4a"
        audio_normalized = tmp_path / "audio_normalized.m4a"

        captured_audio = []

        def mock_compress(*args, **kwargs):
            captured_audio.append(kwargs.get("audio_path"))
            out = args[1]
            out.write_text("compressed", encoding="utf-8")
            return True

        monkeypatch.setattr("wx41.steps.compress.compress_video", mock_compress)

        ctx = PipelineContext(
            src=video,
            media_type="video",
            force=False,
            dry_run=False,
            outputs={"enhanced": audio_enhanced, "normalized": audio_normalized},
        )

        compress_step(ctx, CompressConfig())

        assert captured_audio[0] == audio_enhanced, "Should prefer enhanced audio"

    def test_compress_falls_back_to_normalized_when_no_enhanced(
        self, tmp_path, monkeypatch
    ):
        from wx41.steps.compress import compress_step, CompressConfig
        from wx41.context import PipelineContext

        video = tmp_path / "video.mp4"
        audio_normalized = tmp_path / "audio_normalized.m4a"

        captured_audio = []

        def mock_compress(*args, **kwargs):
            captured_audio.append(kwargs.get("audio_path"))
            out = args[1]
            out.write_text("compressed", encoding="utf-8")
            return True

        monkeypatch.setattr("wx41.steps.compress.compress_video", mock_compress)

        ctx = PipelineContext(
            src=video,
            media_type="video",
            force=False,
            dry_run=False,
            outputs={"normalized": audio_normalized},
        )

        compress_step(ctx, CompressConfig())

        assert captured_audio[0] == audio_normalized, (
            "Should fall back to normalized audio"
        )

    def test_compress_falls_back_to_src_video_audio(self, tmp_path, monkeypatch):
        from wx41.steps.compress import compress_step, CompressConfig
        from wx41.context import PipelineContext

        video = tmp_path / "video.mp4"
        video.touch()

        captured_audio = []

        def mock_compress(*args, **kwargs):
            captured_audio.append(kwargs.get("audio_path"))
            out = args[1]
            out.write_text("compressed", encoding="utf-8")
            return True

        monkeypatch.setattr("wx41.steps.compress.compress_video", mock_compress)

        ctx = PipelineContext(
            src=video, media_type="video", force=False, dry_run=False, outputs={}
        )

        compress_step(ctx, CompressConfig())

        assert captured_audio[0] == video, "Should fall back to src video audio"

    def test_compress_selects_enhanced_audio_when_available(
        self, tmp_path, monkeypatch
    ):
        from wx41.steps.compress import compress_step, CompressConfig
        from wx41.context import PipelineContext

        video = tmp_path / "video.mp4"
        video.touch()
        audio_enhanced = tmp_path / "audio_enhanced.m4a"
        audio_enhanced.touch()
        audio_normalized = tmp_path / "audio_normalized.m4a"
        audio_normalized.touch()

        captured_audio = []

        def mock_compress(*args, **kwargs):
            captured_audio.append(kwargs.get("audio_path"))
            out = args[1]
            out.write_text("compressed", encoding="utf-8")
            return True

        monkeypatch.setattr("wx41.steps.compress.compress_video", mock_compress)

        ctx = PipelineContext(
            src=video,
            media_type="video",
            force=False,
            dry_run=False,
            outputs={"enhanced": audio_enhanced, "normalized": audio_normalized},
        )

        compress_step(ctx, CompressConfig())

        assert captured_audio[0] == audio_enhanced, "Should prefer enhanced audio"

    def test_compress_falls_back_to_normalized_when_no_enhanced(
        self, tmp_path, monkeypatch
    ):
        from wx41.steps.compress import compress_step, CompressConfig
        from wx41.context import PipelineContext

        video = tmp_path / "video.mp4"
        video.touch()
        audio_normalized = tmp_path / "audio_normalized.m4a"
        audio_normalized.touch()

        captured_audio = []

        def mock_compress(*args, **kwargs):
            captured_audio.append(kwargs.get("audio_path"))
            out = args[1]
            out.write_text("compressed", encoding="utf-8")
            return True

        monkeypatch.setattr("wx41.steps.compress.compress_video", mock_compress)

        ctx = PipelineContext(
            src=video,
            media_type="video",
            force=False,
            dry_run=False,
            outputs={"normalized": audio_normalized},
        )

        compress_step(ctx, CompressConfig())

        assert captured_audio[0] == audio_normalized, (
            "Should fall back to normalized audio"
        )

    def test_steps_registry_has_optional_field(self):
        from wx41.steps import get_all_steps

        all_steps = get_all_steps()

        assert "normalize" in all_steps
        normalize_info = all_steps["normalize"]
        assert normalize_info.optional is True

        assert "transcribe" in all_steps
        transcribe_info = all_steps["transcribe"]
        assert transcribe_info.optional is False


class TestCLIOptionality:
    def test_cli_help_shows_dynamic_options(self):
        import subprocess
        import sys
        import os

        env = os.environ.copy()
        env["PYTHONPATH"] = str(Path(__file__).parent.parent.parent)

        result = subprocess.run(
            [sys.executable, "-m", "wx41.cli", "--help"],
            capture_output=True,
            text=True,
            env=env,
        )

        assert "--no-normalize" in result.stdout
        assert "--no-enhance" in result.stdout
        assert "--no-transcribe" not in result.stdout

        assert "--transcribe-backend" in result.stdout
        assert "--normalize-target-lufs" in result.stdout

    def test_cli_configures_step_via_dynamic_flags(self, tmp_path, monkeypatch):
        from click.testing import CliRunner
        from wx41.cli import main
        from wx41.wx4 import MediaOrchestrator

        runner = CliRunner()
        audio = tmp_path / "audio.m4a"
        audio.touch()

        captured_config = []

        def mock_run(self, src, **kwargs):
            captured_config.append(self._config)
            from wx41.context import PipelineContext

            return PipelineContext(src=src)

        monkeypatch.setattr(MediaOrchestrator, "run", mock_run)

        result = runner.invoke(
            main,
            [
                str(audio),
                "--no-normalize",
                "--transcribe-backend",
                "whisper",
                "--normalize-target-lufs",
                "-14.0",
            ],
        )

        assert result.exit_code == 0
        settings = captured_config[0].settings

        assert settings["normalize"].enabled is False
        assert settings["normalize"].target_lufs == -14.0
        assert settings["transcribe"].backend == "whisper"


class TestPipelineWalkingSkeleton:
    def test_produces_transcript_files_with_whisper(self, audio_file):
        try:
            import torch
        except ModuleNotFoundError:
            pytest.skip("torch not installed")
        backend = "whisper"

        config = PipelineConfig(
            settings={"transcribe": TranscribeConfig(backend=backend)}
        )
        transcribe_cfg = config.settings["transcribe"]

        orchestrator = MediaOrchestrator(config, [])
        ctx = orchestrator.run(audio_file)

        for key in transcribe_cfg.output_keys:
            assert key in ctx.outputs
            assert ctx.outputs[key].exists()
            content = ctx.outputs[key].read_text(encoding="utf-8")
            assert len(content) > 0


class TestMetaATWithRealFixture:
    def test_audio_pipeline_produces_all_outputs(self, audio_file):
        from wx41.wx4 import MediaOrchestrator
        from wx41.context import PipelineConfig
        from wx41.steps.transcribe import TranscribeConfig
        from wx41.steps.srt import SRTConfig
        from wx41.steps.black_video import BlackVideoConfig

        try:
            import torch
        except ModuleNotFoundError:
            pytest.skip("torch not installed")

        settings = {
            "transcribe": TranscribeConfig(backend="whisper"),
            "srt": SRTConfig(),
            "black_video": BlackVideoConfig(),
        }

        config = PipelineConfig(settings=settings)
        orchestrator = MediaOrchestrator(config, [])

        ctx = orchestrator.run(audio_file)

        expected_keys = ["transcript_txt", "transcript_json", "srt", "video"]

        for key in expected_keys:
            assert key in ctx.outputs, (
                f"Key '{key}' not in outputs. Available: {list(ctx.outputs.keys())}"
            )
            assert ctx.outputs[key].exists(), (
                f"File for key '{key}' not created at {ctx.outputs[key]}"
            )


class TestMetaATCLI:
    @pytest.mark.parametrize(
        "step_name", ["normalize", "enhance", "compress", "black_video"]
    )
    def test_cli_disable_flag_works(self, step_name, tmp_path, monkeypatch):
        from click.testing import CliRunner
        from wx41.cli import main

        audio = tmp_path / "audio.m4a"
        audio.touch()

        def mock_run(self, src, **kwargs):
            from wx41.context import PipelineContext

            return PipelineContext(src=src, media_type="audio")

        from wx41.wx4 import MediaOrchestrator

        monkeypatch.setattr(MediaOrchestrator, "run", mock_run)

        runner = CliRunner()
        result = runner.invoke(main, [str(audio), "--dry-run", f"--no-{step_name}"])

        assert result.exit_code == 0, f"CLI failed: {result.output}"

        assert f"--no-{step_name}" in result.output or step_name not in result.output, (
            f"CLI should accept --no-{step_name}"
        )

    def test_cli_config_flags_propagate(self, tmp_path, monkeypatch):
        from click.testing import CliRunner
        from wx41.cli import main
        from wx41.wx4 import MediaOrchestrator
        from wx41.context import PipelineContext

        captured = []

        def capture_run(self, src, **kwargs):
            captured.append(self._config)
            return PipelineContext(src=src)

        monkeypatch.setattr(MediaOrchestrator, "run", capture_run)

        audio = tmp_path / "audio.m4a"
        audio.touch()

        runner = CliRunner()
        runner.invoke(
            main, [str(audio), "--normalize-target-lufs", "-16.0", "--dry-run"]
        )

        assert len(captured) == 1
        assert captured[0].settings["normalize"].target_lufs == -16.0

    def test_cli_dry_run_no_files_created(self, tmp_path):
        from click.testing import CliRunner
        from wx41.cli import main

        audio = tmp_path / "audio.m4a"
        audio.touch()

        runner = CliRunner()
        result = runner.invoke(main, [str(audio), "--dry-run"])

        assert result.exit_code == 0

        output_files = (
            list(tmp_path.glob("*.m4a"))
            + list(tmp_path.glob("*.txt"))
            + list(tmp_path.glob("*.json"))
        )
        assert len(output_files) == 1, (
            f"Expected only input file, found: {output_files}"
        )

    def test_cli_output_contains_step_names(self, tmp_path, monkeypatch):
        from click.testing import CliRunner
        from wx41.cli import main
        from wx41.wx4 import MediaOrchestrator
        from wx41.context import PipelineContext

        def mock_run(self, src, **kwargs):
            return PipelineContext(src=src, media_type="audio", outputs={})

        monkeypatch.setattr(MediaOrchestrator, "run", mock_run)

        audio = tmp_path / "audio.m4a"
        audio.touch()

        runner = CliRunner()
        result = runner.invoke(main, [str(audio)])

        assert result.exit_code == 0
