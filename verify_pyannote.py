# verify_pyannote.py

import logging
import sys

from rich.console import Console

console = Console()
logger = logging.getLogger("verify_pyannote")
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

def verify_pyannote() -> None:
    try:
        import pyannote.audio
        version = pyannote.audio.__version__
        console.print(f"[bold green]pyannote.audio versión:[/bold green] {version}")
    except ImportError as e:
        logger.error(f"pyannote.audio no está instalado: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error al verificar pyannote.audio: {e}")
        sys.exit(1)

if __name__ == "__main__":
    verify_pyannote()
