# diarization_cli.py
"""Interfaz de línea de comandos para la herramienta de diarización."""

import argparse
import logging
from pathlib import Path
from typing import Optional

from logging_config import LogConfig, configure_logging, LogLevel
from input_media import load_audio, get_optimal_device
from diarization import (
    DiarizationResult, 
    create_pipeline, 
    format_diarization_result,  # Actualizado
    perform_diarization
)
from lazy_loading import get_loading_times


def parse_arguments() -> argparse.Namespace:
    """Parsea los argumentos de línea de comandos.
    
    Returns:
        Namespace con los argumentos parseados
    """
    parser = argparse.ArgumentParser(description="Diarización de locutores con pyannote.audio")
    parser.add_argument("audio_path", type=Path, help="Ruta al archivo de audio (formato WAV)")
    parser.add_argument("--num_speakers", type=int, default=None, help="Número de locutores (opcional)")
    parser.add_argument("--hf_token", type=str, required=True, help="Token de acceso de Hugging Face")
    parser.add_argument("--device", type=str, choices=["cuda", "cpu"], default=None, 
                       help="Dispositivo para inferencia (por defecto: auto)")
    parser.add_argument("--log_level", type=str, choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                        default="INFO", help="Nivel de logging")
    parser.add_argument("--log_file", type=str, help="Ruta para guardar logs en archivo (opcional)")
    return parser.parse_args()


def setup_cli_logging(args: argparse.Namespace) -> None:
    """Configura el logging basado en los argumentos CLI.
    
    Args:
        args: Argumentos de línea de comandos
    """
    # Crear configuración de logging basada en argumentos CLI
    log_config = LogConfig(
        level=LogLevel[args.log_level],
        log_file=args.log_file
    )
    
    # Aplicar configuración
    configure_logging(log_config)


def display_loading_times() -> None:
    """Muestra los tiempos de carga de los módulos."""
    logger = logging.getLogger("diarization_loading_times")
    loading_times = get_loading_times()
    
    if loading_times:
        logger.info("Tiempos de carga de módulos:")
        for module_name, load_time in loading_times.items():
            logger.info(f"  - {module_name}: {load_time:.4f}s")
    else:
        logger.info("No se registraron tiempos de carga")


def display_results(result: DiarizationResult) -> None:
    """Muestra los resultados de diarización de manera formateada."""
    logger = logging.getLogger("diarization_results")
    info = format_diarization_result(result)  # Actualizado
    metrics = info["metrics"]
    
    logger.info(f"Duración del audio: {metrics['audio_duration']} segundos")
    logger.info(f"Tiempo de procesamiento: {metrics['processing_time']} segundos")
    logger.info(f"Factor de velocidad: {metrics['speed_factor']}x")


def run_diarization_cli() -> None:
    """Ejecuta el flujo principal de la aplicación CLI."""
    # Obtener argumentos
    args = parse_arguments()
    
    # Configurar logging
    setup_cli_logging(args)
    logger = logging.getLogger("diarization_cli")
    
    # Preparar pipeline
    logger.info(f"Cargando pipeline de diarización...")
    pipeline = create_pipeline(args.hf_token, args.device)
    
    # Cargar audio
    logger.info(f"Cargando archivo de audio: {args.audio_path}")
    audio_data = load_audio(args.audio_path, args.device)
    
    # Realizar diarización
    logger.info("Iniciando proceso de diarización...")
    result = perform_diarization(pipeline, audio_data, args.num_speakers)
    
    # Mostrar resultados
    display_results(result)
    
    # Mostrar tiempos de carga si se solicita
    display_loading_times()


if __name__ == "__main__":
    run_diarization_cli()