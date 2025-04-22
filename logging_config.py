# logging_config.py
"""Configuración centralizada para logging en la aplicación de diarización."""

import logging
import os
import sys
import warnings
from typing import Optional

from rich.console import Console
from rich.logging import RichHandler

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, TypedDict, Union


class LogLevel(Enum):
    """Niveles de logging disponibles.
    
    Miembros:
        DEBUG: Nivel de logging detallado para depuración
        INFO: Información general sobre el progreso
        WARNING: Advertencias que no impiden la ejecución
        ERROR: Errores que afectan a una operación específica
        CRITICAL: Errores críticos que impiden continuar
    """
    DEBUG = 10  # logging.DEBUG
    INFO = 20   # logging.INFO
    WARNING = 30  # logging.WARNING
    ERROR = 40  # logging.ERROR
    CRITICAL = 50  # logging.CRITICAL


@dataclass(frozen=True)
class LogConfig:
    """Configuración inmutable para logging.
    
    Attributes:
        level: Nivel de logging a utilizar
        format: Formato de los mensajes de log
        datefmt: Formato de las marcas de tiempo
        use_rich_handler: Si se debe usar el manejador enriquecido
        rich_tracebacks: Si se deben mostrar trazas de error enriquecidas
        rich_markup: Si se debe permitir marcado en mensajes de log
        log_file: Ruta al archivo de log (opcional)
    """
    level: LogLevel = LogLevel.INFO
    format: str = "%(message)s"
    datefmt: str = "[%X]"
    use_rich_handler: bool = True
    rich_tracebacks: bool = True
    rich_markup: bool = True
    log_file: Optional[str] = None


# Lista de patrones de advertencias a filtrar
FILTERED_WARNINGS = [
    "torchaudio._backend.set_audio_backend has been deprecated",
    "torchaudio._backend.get_audio_backend has been deprecated",
    "`torchaudio.backend.common.AudioMetaData` has been moved",
    "TensorFloat-32 \(TF32\) has been disabled",
    "std\(\): degrees of freedom is <= 0",
    "Module 'speechbrain.pretrained' was deprecated"
]

# Módulos cuyos warnings serán completamente ignorados
IGNORED_WARNING_MODULES = [
    "pyannote.audio.utils.reproducibility",
    "pyannote.audio.models.blocks.pooling"
]

# Niveles de log para bibliotecas específicas
LIBRARY_LOG_LEVELS = {
    "speechbrain": logging.WARNING,
    "pyannote": logging.INFO,
    "torchaudio": logging.WARNING,
    "torch": logging.WARNING,
    "urllib3": logging.WARNING,
    "matplotlib": logging.WARNING,
    "checkpoint": logging.WARNING,
    "requests": logging.WARNING,
    "huggingface_hub": logging.WARNING,
    "transformers": logging.ERROR,
}


def configure_env_variables() -> None:
    """Configura variables de entorno para silenciar mensajes de bibliotecas."""
    os.environ["TRANSFORMERS_VERBOSITY"] = "error"
    os.environ["PYTHONWARNINGS"] = "ignore::UserWarning"


def configure_warnings(level: int = logging.INFO) -> None:
    """Configura filtros para advertencias.
    
    Args:
        level: Nivel de logging actual
    """
    # Ignorar FutureWarnings globalmente
    warnings.filterwarnings("ignore", category=FutureWarning)
    
    # Filtrar patrones específicos
    for pattern in FILTERED_WARNINGS:
        warnings.filterwarnings("ignore", message=f".*{pattern}.*")
    
    # Filtrar módulos específicos
    for module in IGNORED_WARNING_MODULES:
        warnings.filterwarnings("ignore", module=module)
    
    # Si no estamos en modo DEBUG, filtrar todas las advertencias
    if level > logging.DEBUG:
        warnings.filterwarnings("ignore")


def configure_library_logging() -> None:
    """Configura niveles de logging para bibliotecas específicas."""
    for lib, level in LIBRARY_LOG_LEVELS.items():
        logging.getLogger(lib).setLevel(level)
    
    # Ajustes adicionales específicos
    logging.getLogger("speechbrain.utils.quirks").setLevel(logging.WARNING)
    logging.getLogger("torio._extension.utils").setLevel(logging.ERROR)
    logging.getLogger("checkpoint").setLevel(logging.INFO)


def configure_logging(config: LogConfig = LogConfig()) -> None:
    """Configura el sistema de logging global según la configuración proporcionada.
    
    Args:
        config: Configuración de logging a aplicar
    """
    # Configurar variables de entorno
    configure_env_variables()
    
    # Configurar filtros de advertencias
    configure_warnings(config.level.value)
    
    # Crear consola Rich y handlers
    console = Console(markup=config.rich_markup)
    handlers = []
    
    # Configurar handler para consola (rich o básico)
    console_handler = RichHandler(
        console=console,
        rich_tracebacks=config.rich_tracebacks,
        markup=config.rich_markup,
        show_time=True,
        show_path=True
    )
    handlers.append(console_handler)

    
    # Configurar logger para archivo si se especifica
    if config.log_file:
        file_handler = logging.FileHandler(config.log_file)
        file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(file_formatter)
        handlers.append(file_handler)
    
    # Configurar logger raíz
    logging.basicConfig(
        level=config.level.value,
        format=config.format,
        datefmt=config.datefmt,
        handlers=handlers,
        force=True
    )
    
    # Configurar niveles de logger para bibliotecas específicas
    configure_library_logging()
    
    # Configurar logger principal de la aplicación
    app_logger = logging.getLogger("diarization")
    app_logger.setLevel(config.level.value)
    
    # Mensaje de debug si estamos en modo debug
    if config.level.value <= LogLevel.DEBUG.value:
        app_logger.debug("Logging configurado en modo DEBUG")