"""
Test end-to-end del CLI con la nueva funcionalidad de agrupación.
"""

import pytest
from pathlib import Path
import tempfile
from typer.testing import CliRunner
from wx3 import app

runner = CliRunner()


def test_cli_help_shows_long_option():
    """Verifica que la opción --long aparece en la ayuda."""
    result = runner.invoke(app, ["transcribe", "--help"])
    assert result.exit_code == 0
    assert "--long" in result.stdout
    assert "-lg" in result.stdout


def test_cli_process_help_shows_long_option():
    """Verifica que la opción --long aparece en process."""
    result = runner.invoke(app, ["process", "--help"])
    assert result.exit_code == 0
    assert "--long" in result.stdout
    assert "-lg" in result.stdout


def test_cli_help_shows_max_chars_option():
    """Verifica que la opción --max-chars aparece en la ayuda."""
    result = runner.invoke(app, ["transcribe", "--help"])
    assert result.exit_code == 0
    assert "--max-chars" in result.stdout


def test_cli_help_shows_max_duration_option():
    """Verifica que la opción --max-duration aparece en la ayuda."""
    result = runner.invoke(app, ["transcribe", "--help"])
    assert result.exit_code == 0
    assert "--max-duration" in result.stdout


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
