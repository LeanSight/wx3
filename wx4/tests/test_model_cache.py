"""
Tests for wx4.model_cache module.
"""

import pytest
from unittest.mock import MagicMock


def test_get_model_loads_once():
    """Loader should be called only once for the same model name."""
    from wx4.model_cache import _get_model, _clear_model_cache

    _clear_model_cache()

    calls = []
    loader = lambda: calls.append(1) or "model"

    result1 = _get_model("TestModel", loader, None)
    result2 = _get_model("TestModel", loader, None)

    assert result1 == "model"
    assert result2 == "model"
    assert len(calls) == 1


def test_get_model_different_names_load_both():
    """Different model names should each be loaded."""
    from wx4.model_cache import _get_model, _clear_model_cache

    _clear_model_cache()

    calls = []
    loader1 = lambda: calls.append("a") or "model_a"
    loader2 = lambda: calls.append("b") or "model_b"

    result1 = _get_model("ModelA", loader1, None)
    result2 = _get_model("ModelB", loader2, None)

    assert result1 == "model_a"
    assert result2 == "model_b"
    assert len(calls) == 2


def test_get_model_console_none_no_print():
    """console=None should not print anything."""
    from wx4.model_cache import _get_model, _clear_model_cache

    _clear_model_cache()

    console = None
    loader = lambda: "model"

    result = _get_model("TestModel", loader, console)
    assert result == "model"


def test_get_model_console_arg_prints():
    """console with a value should print Loading message."""
    from wx4.model_cache import _get_model, _clear_model_cache

    _clear_model_cache()

    console = MagicMock()
    loader = lambda: "model"

    result = _get_model("TestModel", loader, console)

    assert result == "model"
    console.print.assert_called_once_with("Loading TestModel...")


def test_clear_model_cache():
    """_clear_model_cache should empty the cache."""
    from wx4.model_cache import _get_model, _clear_model_cache, _model_cache

    _clear_model_cache()

    _get_model("TestModel", lambda: "v1", None)
    assert "TestModel" in _model_cache

    _clear_model_cache()
    assert len(_model_cache) == 0
