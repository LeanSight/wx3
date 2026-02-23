"""
File-based cache for enhance pipeline results.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional

DEFAULT_CACHE = Path.cwd() / ".enhance_meeting_cache.json"


def file_key(path: Path) -> str:
    """Return '<name>|<size>|<mtime>' cache key for a file."""
    s = path.stat()
    return f"{path.name}|{s.st_size}|{s.st_mtime}"


def load_cache(cache_path: Optional[Path] = None) -> Dict[str, Any]:
    """Load cache from JSON file. Returns empty dict if missing or corrupt."""
    if cache_path is None:
        cache_path = DEFAULT_CACHE

    if cache_path.exists():
        try:
            return json.loads(cache_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, IOError):
            return {}

    return {}


def save_cache(cache: Dict[str, Any], cache_path: Optional[Path] = None) -> None:
    """Save cache dict to JSON file."""
    if cache_path is None:
        cache_path = DEFAULT_CACHE

    cache_path.write_text(
        json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8"
    )
