# transcription.py
"""Módulo de transcripción de audio con Whisper."""

import logging
import time
from typing import Any, Dict, List, Optional, Tuple, TypedDict, Union, Callable
from dataclasses import dataclass

from rich.progress import Progress, TextColumn, BarColumn, TimeElapsedColumn
from lazy_loading import lazy_load

from constants import (
    DEFAULT_CHUNK_LENGTH, DEFAULT_BATCH_SIZE, DEFAULT_LANGUAGE,
    DEFAULT_TASK, DEFAULT_ATTN_TYPE, get_model_kwargs
)

# Configurar logger
logger = logging.getLogger("transcription.core")

# Definiciones de tipos específicos de transcripción
class TranscriptChunk(TypedDict):
    """Segmento de transcripción con texto y marcas de tiempo."""
    text: str
    timestamp: Tuple[Optional[float], Optional[float]]

class TranscriptionMetrics(TypedDict):
    """Métricas de rendimiento del proceso de transcripción."""
    audio_duration: float
    processing_time: float
    speed_factor: float

class TranscriptionInfo(TypedDict):
    """Información completa del resultado de transcripción."""
    text: str
    chunks: List[TranscriptChunk]
    metrics: TranscriptionMetrics

@dataclass(frozen=True)
class TranscriptionResult:
    """Estructura inmutable para resultados de transcripción."""
    text: str
    chunks: List[TranscriptChunk]
    audio_duration: float
    processing_time: float
    speed_factor: float


def with_progress_bar(description: str, func: Callable) -> Any:
    """
    Ejecuta una función mientras muestra una barra de progreso.
    
    Args:
        description: Descripción para la barra de progreso
        func: Función a ejecutar
        
    Returns:
        Resultado de la función
    """
    with Progress(
        TextColumn("🤗 [progress.description]{task.description}"),
        BarColumn(style="yellow1", pulse_style="white"),
        TimeElapsedColumn(),
    ) as progress:
        task_id = progress.add_task(f"[yellow]{description}", total=None)
        return func()


def create_pipeline(model_name: str, device: Optional[str] = None, attn_type: str = DEFAULT_ATTN_TYPE) -> Any:
    """Crea y devuelve un pipeline de transcripción.

    Args:
        model_name: Nombre del modelo de Whisper a utilizar
        device: Dispositivo para inferencia ('cuda', 'cpu', o None para auto)
        attn_type: Tipo de atención a utilizar ('sdpa', 'eager', 'flash')

    Returns:
        Pipeline configurado para transcripción
    """
    # Carga perezosa de los módulos necesarios
    transformers = lazy_load("transformers", "")
    torch = lazy_load("torch", "")
    
    # Determinar el dispositivo adecuado si no se especifica
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    
    # Configurar opciones del modelo
    model_kwargs = get_model_kwargs(attn_type)
    
    # Crear pipeline de whisper
    pipeline = transformers.pipeline(
        "automatic-speech-recognition",
        model=model_name,
        torch_dtype=torch.float16,  # Usar precisión media para eficiencia
        device=device,
        model_kwargs=model_kwargs
    )
    
    return pipeline


def perform_transcription(
    pipeline: Any,
    audio_data: Dict[str, Any],
    task: str = DEFAULT_TASK.value,
    language: Optional[str] = DEFAULT_LANGUAGE,
    chunk_length: int = DEFAULT_CHUNK_LENGTH,
    batch_size: int = DEFAULT_BATCH_SIZE
) -> TranscriptionResult:
    """Realiza la transcripción en los datos de audio proporcionados.

    Args:
        pipeline: Pipeline de transcripción configurado
        audio_data: Datos de audio (waveform y sample_rate)
        task: Tarea a realizar ("transcribe" o "translate")
        language: Código de idioma (ej: "es", "en"). None para detección automática
        chunk_length: Duración en segundos de cada segmento para procesar
        batch_size: Tamaño de batch para procesamiento en GPU

    Returns:
        Resultado de transcripción con métricas de rendimiento
    """
    # Carga perezosa de numpy
    np = lazy_load("numpy", "")
    
    # Preparar el audio para whisper
    waveform = audio_data["waveform"]
    sample_rate = audio_data["sample_rate"]
    audio_np = waveform.squeeze().cpu().numpy()
    
    # Configurar parámetros de generación
    generate_kwargs = {"task": task}
    if language:  # Solo agregar language si no es None
        generate_kwargs["language"] = language
    
    # Medición de rendimiento
    start_time = time.time()
    
    logger.info(f"Iniciando transcripción con modelo Whisper...")
    if language:
        logger.info(f"Idioma configurado: {language}")
    else:
        logger.info("Idioma: detección automática")
    
    # Definir la función de transcripción
    def run_transcription():
        return pipeline(
            {"raw": audio_np, "sampling_rate": sample_rate},
            chunk_length_s=chunk_length,
            batch_size=batch_size,
            generate_kwargs=generate_kwargs,
            return_timestamps=True,
        )
    
    # Realizar transcripción con barra de progreso de Rich
    outputs = with_progress_bar("Transcribiendo audio", run_transcription)
    
    # Extraer chunks
    chunks = [
        {"text": ch["text"], "timestamp": (ch["timestamp"][0], ch["timestamp"][1])}
        for ch in outputs.get("chunks", [])
    ]
    
    # Extraer texto completo
    text = " ".join(chunk["text"] for chunk in chunks)
    
    # Cálculo de métricas de rendimiento
    end_time = time.time()
    processing_time = end_time - start_time
    audio_duration = waveform.shape[1] / sample_rate
    
    # Evitar división por cero
    speed_factor = audio_duration / processing_time if processing_time > 0 else float('inf')
    
    logger.info(f"Transcripción completada: {len(chunks)} segmentos generados")
    logger.info(f"Tiempo de procesamiento: {processing_time:.2f}s (factor de velocidad: {speed_factor:.2f}x)")
    
    return TranscriptionResult(
        text=text,
        chunks=chunks,
        audio_duration=audio_duration,
        processing_time=processing_time,
        speed_factor=speed_factor
    )


def format_transcription_result(result: TranscriptionResult) -> TranscriptionInfo:
    """Formatea la información de transcripción para su presentación.

    Args:
        result: Resultado de transcripción

    Returns:
        Diccionario con información de transcripción formateada y métricas
    """
    # Formatea las métricas
    metrics = {
        "audio_duration": round(result.audio_duration, 2),
        "processing_time": round(result.processing_time, 2),
        "speed_factor": round(result.speed_factor, 2)
    }
    
    return {
        "text": result.text,
        "chunks": result.chunks,
        "metrics": metrics
    }