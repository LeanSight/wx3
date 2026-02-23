"""
Tests for wx4/__main__.py - entry point for python -m wx4
"""

from unittest.mock import patch


class TestMain:
    def test_main_invokes_cli_app(self):
        """python -m wx4 must delegate to the Typer app."""
        with patch("wx4.cli.app") as mock_app:
            import wx4.__main__  # noqa: F401 - side-effect import
            mock_app.assert_called_once()
