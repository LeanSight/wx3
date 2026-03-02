from pathlib import Path
import pytest
from wx41.pipeline import MediaOrchestrator
from wx41.context import PipelineConfig
from wx41.steps.transcribe import TranscribeConfig

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
        
        # Test dynamic step-specific options
        assert "--transcribe-backend" in result.stdout
        assert "--normalize-target-lufs" in result.stdout

    def test_cli_configures_step_via_dynamic_flags(self, tmp_path, monkeypatch):
        from click.testing import CliRunner
        from wx41.cli import main
        from wx41.pipeline import MediaOrchestrator
        
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
        
        assert result.exit_code == 0, f"CLI FAILED: {result.output}"
        settings = captured_config[0].settings
        
        assert settings["normalize"].enabled is False
        assert settings["normalize"].target_lufs == -14.0
        assert settings["transcribe"].backend == "whisper"


class TestPipelineWalkingSkeleton:
    def test_produces_transcript_files_with_whisper(self, audio_file):
        try:
            import torch
        except ModuleNotFoundError:
            pytest.skip("torch not installed - this AT requires full dependencies")
        backend = "whisper"
        
        config = PipelineConfig(
            settings={"transcribe": TranscribeConfig(backend=backend)}
        )
        transcribe_cfg = config.settings["transcribe"]
        
        orchestrator = MediaOrchestrator(config, [])
        ctx = orchestrator.run(audio_file)

        for key in transcribe_cfg.output_keys:
            assert key in ctx.outputs, f"{key} not in outputs"
            assert ctx.outputs[key].exists(), f"Output file not found: {key}"
            content = ctx.outputs[key].read_text(encoding="utf-8")
            assert len(content) > 0, f"Output file is empty: {key}"
