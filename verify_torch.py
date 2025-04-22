# verify_torch.py

import logging
import sys

import torch
from rich.console import Console

console = Console()
logger = logging.getLogger("verify_torch")
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

def verify_torch() -> None:
    try:
        version = torch.__version__
        cuda_available = torch.cuda.is_available()
        cuda_device = torch.cuda.get_device_name(0) if cuda_available else "No CUDA device found"

        console.print(f"[bold green]PyTorch versión:[/bold green] {version}")
        console.print(f"[bold green]CUDA disponible:[/bold green] {cuda_available}")
        console.print(f"[bold green]Dispositivo CUDA:[/bold green] {cuda_device}")
    except Exception as e:
        logger.error(f"Error al verificar PyTorch: {e}")
        sys.exit(1)

if __name__ == "__main__":
    verify_torch()
