from pathlib import Path
from typing import Optional, Callable


def measure_lufs(wav: Path) -> float:
    return -23.0


def normalize_lufs(
    src: Path,
    dst: Path,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> bool:
    dst.write_text(f"normalized:{src.name}", encoding="utf-8")
    return True
