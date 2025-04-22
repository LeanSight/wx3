# diarization.py
"""Módulo de diarización de audio con pyannote.audio"""

import logging
import time
from typing import Any, Callable, Dict, List, Optional, TypedDict
from dataclasses import dataclass

from lazy_loading import lazy_load
from constants import DEFAULT_DIARIZATION_MODEL

# Configurar logger
logger = logging.getLogger("diarization.core")

# Definiciones de tipos específicos de diarización
class SpeakerSegment(TypedDict):
    """Segmento de audio asociado a un locutor específico."""
    start: float
    end: float
    speaker: str

class DiarizationMetrics(TypedDict):
    """Métricas de rendimiento del proceso de diarización."""
    audio_duration: float
    processing_time: float
    speed_factor: float

class DiarizationInfo(TypedDict):
    """Información completa del resultado de diarización."""
    metrics: DiarizationMetrics
    speakers: List[SpeakerSegment]

@dataclass(frozen=True)
class DiarizationResult:
    """Estructura inmutable para resultados de diarización."""
    diarization: Any  # pyannote.core.Annotation
    audio_duration: float
    processing_time: float
    speed_factor: float


def create_pipeline(token: str, device: Optional[str] = None) -> Any:
    """Crea y devuelve un pipeline de diarización.

    Args:
        token: Token de acceso de Hugging Face
        device: Dispositivo para inferencia ('cuda', 'cpu', o None para auto)

    Returns:
        Pipeline configurado para diarización
    """
    # Carga perezosa de los módulos necesarios
    Pipeline = lazy_load("pyannote.audio", "Pipeline")
    torch = lazy_load("torch", "")
    
    pipeline = Pipeline.from_pretrained(
        DEFAULT_DIARIZATION_MODEL,
        use_auth_token=token
    )
    
    # Determinar el dispositivo adecuado si no se especifica
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    
    # Usar el módulo torch para crear el dispositivo
    pipeline.to(torch.device(device))
    
    return pipeline


def perform_diarization(
    pipeline: Any, 
    audio_data: Dict[str, Any], 
    num_speakers: Optional[int] = None,
    progress_hook: Optional[Callable] = None
) -> DiarizationResult:
    """Realiza la diarización en los datos de audio proporcionados.

    Args:
        pipeline: Pipeline de diarización configurado
        audio_data: Datos de audio (waveform y sample_rate)
        num_speakers: Número de locutores (opcional)
        progress_hook: Función de callback para el progreso (opcional)

    Returns:
        Resultado de diarización con métricas de rendimiento
    """
    pipeline_args = {"num_speakers": num_speakers} if num_speakers else {}
    
    # Cargar ProgressHook solo si es necesario
    if progress_hook is None:
        # Cargar el módulo y clase directamente
        pyannote_hooks = lazy_load("pyannote.audio.pipelines.utils.hook", "")
        hook = pyannote_hooks.ProgressHook()
    else:
        hook = progress_hook

    # Medición de rendimiento
    start_time = time.time()
    
    # Contexto para el hook de progreso
    context_manager = hook if hasattr(hook, "__enter__") else nullcontext(hook)
    
    with context_manager as h:
        diarization = pipeline(audio_data, hook=h, **pipeline_args)
    
    # Cálculo de métricas de rendimiento
    end_time = time.time()
    processing_time = end_time - start_time
    audio_duration = audio_data["waveform"].shape[1] / audio_data["sample_rate"]
    
    # Evitar división por cero
    speed_factor = audio_duration / processing_time if processing_time > 0 else float('inf')

    logger.info(
        "Diarización completada: %.2fs de audio, %.2fs de proceso (×%.2f)",
        audio_duration, processing_time, speed_factor
    )
    
    return DiarizationResult(
        diarization=diarization,
        audio_duration=audio_duration,
        processing_time=processing_time,
        speed_factor=speed_factor
    )


def format_diarization_result(result: DiarizationResult) -> DiarizationInfo:
    """Formatea la información de diarización para su presentación.

    Args:
        result: Resultado de diarización

    Returns:
        Diccionario con información de diarización formateada y métricas
    """
    # Extrae los tracks directamente
    speakers = [
        {
            "start": turn.start, 
            "end": turn.end, 
            "speaker": speaker
        }
        for turn, _, speaker in result.diarization.itertracks(yield_label=True)
    ]
    
    # Formatea las métricas
    metrics = {
        "audio_duration": round(result.audio_duration, 2),
        "processing_time": round(result.processing_time, 2),
        "speed_factor": round(result.speed_factor, 2)
    }
    
    return {
        "metrics": metrics,
        "speakers": speakers
    }


# Utilidad para el manejo de contexto vacío
class nullcontext:
    """Un contexto que no hace nada, útil para condicionales."""
    def __init__(self, enter_result=None):
        self.enter_result = enter_result
    
    def __enter__(self):
        return self.enter_result
    
    def __exit__(self, *excinfo):
        pass