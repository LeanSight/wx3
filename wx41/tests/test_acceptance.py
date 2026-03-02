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
        
        audio = tmp_path / "audio.m4a"
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
            assert expected_path.exists(), f"El step {step_name} no produjo el archivo para la llave {key}"

    def test_step_cli_resumability(self, step_name, tmp_path, monkeypatch):
        from click.testing import CliRunner
        from wx41.cli import main
        from wx41.steps import STEP_REGISTRY, get_all_steps
        import dataclasses
        
        audio = tmp_path / "audio.m4a"
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
            
        audio = tmp_path / "audio.m4a"
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
        
        audio = tmp_path / "audio.m4a"
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


class TestStepOptionality:
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
            env=env
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
        
        result = runner.invoke(main, [
            str(audio), 
            "--no-normalize", 
            "--transcribe-backend", "whisper",
            "--normalize-target-lufs", "-14.0"
        ])
        
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
