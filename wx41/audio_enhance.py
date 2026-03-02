from pathlib import Path
from typing import Optional, Callable


def apply_clearvoice(
    src: Path,
    dst: Path,
    model_path: Optional[Path] = None,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> bool:
    dst.write_text(f"enhanced:{src.name}", encoding="utf-8")
    return True
