# verify_system.py

import sys
import shutil
import logging

from rich.console import Console

console = Console()
logger = logging.getLogger("verify")
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# ──────────────────────────────────────────────
# Torch verification
# ──────────────────────────────────────────────

def verify_torch() -> None:
    try:
        import torch
        version = torch.__version__
        cuda_available = torch.cuda.is_available()
        cuda_device = torch.cuda.get_device_name(0) if cuda_available else "No CUDA device found"

        console.print(f"[bold green]✔ PyTorch detected:[/bold green] v{version}")
        console.print(f"[green]CUDA available:[/green] {cuda_available}")
        console.print(f"[green]CUDA device:[/green] {cuda_device}")
    except ImportError as e:
        logger.error(f"❌ PyTorch is not installed: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Error checking PyTorch: {e}")
        sys.exit(1)

# ──────────────────────────────────────────────
# PyAnnote verification
# ──────────────────────────────────────────────

def verify_pyannote() -> None:
    try:
        import pyannote.audio
        version = pyannote.audio.__version__
        console.print(f"[bold green]✔ pyannote.audio detected:[/bold green] v{version}")
    except ImportError as e:
        logger.error(f"❌ pyannote.audio is not installed: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Error checking pyannote.audio: {e}")
        sys.exit(1)

# ──────────────────────────────────────────────
# ffmpeg verification
# ──────────────────────────────────────────────

def verify_ffmpeg() -> None:
    path = shutil.which("ffmpeg")
    if path:
        console.print(f"[bold green]✔ ffmpeg detected:[/bold green] {path}")
    else:
        console.print("[bold yellow]⚠️ ffmpeg not found in system PATH.[/bold yellow]")
        console.print("[yellow]PyAV may fail when processing video files.[/yellow]")
        console.print("[yellow]Please install ffmpeg and ensure it is available in your command line.[/yellow]")

# ──────────────────────────────────────────────
# Combined entry point (optional)
# ──────────────────────────────────────────────

if __name__ == "__main__":
    console.rule("[bold]System Verification")
    verify_torch()
    verify_pyannote()
    verify_ffmpeg()
