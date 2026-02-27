"""
Model cache for lazy loading.

Provides _get_model function that loads models on demand and caches them.
"""

from typing import Any, Callable, Optional

from rich.console import Console

_model_cache: dict[str, Any] = {}


def _get_model(
    name: str,
    loader: Callable[[], Any],
    console: Optional[Console] = None,
) -> Any:
    """
    Load a model lazily, only the first time it's needed.

    Shows 'Loading {name}...' only on first load if console is provided.
    Caches the model for subsequent uses.

    Args:
        name: Name of the model for display and cache
        loader: Zero-argument function that returns the model
        console: Optional Console for displaying messages. If None, no message is printed.

    Returns:
        Loaded model (from cache or newly loaded)
    """
    if name not in _model_cache:
        if console is not None:
            console.print(f"Loading {name}...")
        _model_cache[name] = loader()
    return _model_cache[name]


def _clear_model_cache() -> None:
    """Clear the model cache. Useful for testing."""
    _model_cache.clear()
