# transcription_cli.py
"""Interfaz de línea de comandos para la herramienta de transcripción."""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Optional

from logging_config import LogConfig, configure_logging, LogLevel
from input_media import load_audio, get_optimal_device
from transcription import (
    TranscriptionResult,
    create_pipeline,
    format_transcription_result,
    perform_transcription
)
from lazy_loading import get_loading_times


def parse_arguments() -> argparse.Namespace:
    """Parsea los argumentos de línea de comandos.
    
    Returns:
        Namespace con los argumentos parseados
    """
    parser = argparse.ArgumentParser(description="Transcripción de audio con Whisper")
    parser.add_argument("audio_path", type=Path, help="Ruta al archivo de audio")
    parser.add_argument("--model", type=str, default="openai/whisper-large-v3", 
                       help="Modelo de Whisper a utilizar")
    parser.add_argument("--task", type=str, choices=["transcribe", "translate"], default="transcribe",
                       help="Tarea a realizar: transcribe o translate")
    parser.add_argument("--lang", type=str, default="es", 
                       help="Código de idioma (ej: 'es', 'en')")
    parser.add_argument("--chunk_length", type=int, default=30, 
                       help="Duración en segundos de cada chunk para transcripción")
    parser.add_argument("--batch_size", type=int, default=8, 
                       help="Tamaño de batch para procesamiento en GPU")
    parser.add_argument("--attn_type", type=str, choices=["sdpa", "eager", "flash"], default="sdpa", 
                       help="Tipo de atención a utilizar")
    parser.add_argument("--device", type=str, choices=["cuda", "cpu"], default=None, 
                       help="Dispositivo para inferencia (por defecto: auto)")
    parser.add_argument("--output", type=str, help="Ruta para guardar resultado (opcional)")
    parser.add_argument("--format", type=str, choices=["json", "txt", "srt", "vtt"], default="json",
                       help="Formato de salida")
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
    logger = logging.getLogger("transcription_loading_times")
    loading_times = get_loading_times()
    
    if loading_times:
        logger.info("Tiempos de carga de módulos:")
        for module_name, load_time in loading_times.items():
            logger.info(f"  - {module_name}: {load_time:.4f}s")
    else:
        logger.info("No se registraron tiempos de carga")


def display_results(result: TranscriptionResult) -> None:
    """Muestra los resultados de transcripción de manera formateada.
    
    Args:
        result: Resultado de la transcripción
    """
    logger = logging.getLogger("transcription_results")
    info = format_transcription_result(result)
    metrics = info["metrics"]
    
    logger.info(f"Duración del audio: {metrics['audio_duration']} segundos")
    logger.info(f"Tiempo de procesamiento: {metrics['processing_time']} segundos")
    logger.info(f"Factor de velocidad: {metrics['speed_factor']}x")
    
    # Mostrar texto completo (solo las primeras líneas si es muy largo)
    text_lines = result.text.split("\n")
    preview_lines = text_lines[:5]
    if len(text_lines) > 5:
        preview_lines.append("...")


def save_results(result: TranscriptionResult, output_path: str, format_type: str) -> None:
    """Guarda los resultados en el formato especificado.
    
    Args:
        result: Resultado de la transcripción
        output_path: Ruta donde guardar el resultado
        format_type: Formato de salida ('json', 'txt', 'srt', 'vtt')
    """
    logger = logging.getLogger("transcription_output")
    
    # Si no se especifica ruta, crear una basada en el formato
    if not output_path:
        output_path = f"transcription_result.{format_type}"
    
    # Asegurar que la extensión coincida con el formato
    if not output_path.endswith(f".{format_type}"):
        output_path = f"{Path(output_path).with_suffix('')}.{format_type}"
    
    logger.info(f"Guardando resultado en: {output_path}")
    
    # Guardar según formato
    if format_type == "json":
        info = format_transcription_result(result)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(info, f, ensure_ascii=False, indent=2)
    
    elif format_type == "txt":
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(result.text)
    
    elif format_type in ["srt", "vtt"]:
        # Implementación básica de conversión a formatos de subtítulos
        logger.warning(f"Formato {format_type} no completamente implementado. Guardando en formato simple.")
        with open(output_path, 'w', encoding='utf-8') as f:
            for i, chunk in enumerate(result.chunks, 1):
                start, end = chunk["timestamp"]
                if start is not None and end is not None:
                    # Formato básico de subtítulos
                    if format_type == "srt":
                        f.write(f"{i}\n")
                        f.write(f"{format_timestamp_srt(start)} --> {format_timestamp_srt(end)}\n")
                        f.write(f"{chunk['text']}\n\n")
                    else:  # vtt
                        if i == 1:
                            f.write("WEBVTT\n\n")
                        f.write(f"{format_timestamp_vtt(start)} --> {format_timestamp_vtt(end)}\n")
                        f.write(f"{chunk['text']}\n\n")
    
    logger.info(f"Resultado guardado exitosamente en {output_path}")


def format_timestamp_srt(seconds: float) -> str:
    """Formatea un timestamp en segundos al formato SRT (HH:MM:SS,mmm)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{int(seconds):02d},{int((seconds % 1) * 1000):03d}"


def format_timestamp_vtt(seconds: float) -> str:
    """Formatea un timestamp en segundos al formato VTT (HH:MM:SS.mmm)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{int(seconds):02d}.{int((seconds % 1) * 1000):03d}"


def run_transcription_cli() -> int:
    """Ejecuta el flujo principal de la aplicación CLI.
    
    Returns:
        Código de salida (0 éxito, 1 error)
    """
    try:
        # Obtener argumentos
        args = parse_arguments()
        
        # Configurar logging
        setup_cli_logging(args)
        logger = logging.getLogger("transcription_cli")
        
        # Preparar pipeline
        logger.info(f"Cargando pipeline de transcripción con modelo {args.model}...")
        pipeline = create_pipeline(args.model, args.device, args.attn_type)
        
        # Cargar audio
        logger.info(f"Cargando archivo de audio: {args.audio_path}")
        audio_data = load_audio(args.audio_path, args.device)
        
        # Realizar transcripción
        logger.info(f"Iniciando proceso de transcripción (tarea: {args.task}, idioma: {args.lang})...")
        result = perform_transcription(
            pipeline,
            audio_data,
            task=args.task,
            language=args.lang,
            chunk_length=args.chunk_length,
            batch_size=args.batch_size
        )
        
        # Mostrar resultados
        display_results(result)
        
        # Guardar resultados si se especifica
        if args.output or args.format:
            save_results(result, args.output, args.format)
        
        # Mostrar tiempos de carga si se solicita
        display_loading_times()
            
        logger.info("Proceso de transcripción completado con éxito")
        return 0
        
    except Exception as e:
        logger = logging.getLogger("transcription_cli")
        logger.error(f"Error durante el proceso de transcripción: {str(e)}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(run_transcription_cli())