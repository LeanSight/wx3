# diarization.py
# Módulo de diarización de audio con pyannote.audio y extracción de embeddings

import logging
import time
from typing import Any, Dict, List, TypedDict, Tuple
from dataclasses import dataclass
from pathlib import Path

from lazy_loading import lazy_load
from constants import DEFAULT_DIARIZATION_MODEL

# Configuración de logger
logger = logging.getLogger("diarization.core")

# Modelos predeterminados
EMBEDDING_MODEL = "pyannote/embedding"

# Definiciones de tipos específicos de diarización
class SpeakerSegment(TypedDict):
    """Segmento de audio asociado a un locutor específico."""
    start: float
    end: float
    speaker: str
    embedding: List[float]

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
    segments: List[Tuple[Any, str, List[float]]]

class nullcontext:
    """Un contexto que no hace nada, útil para condicionales."""
    def __init__(self, enter_result=None):
        self.enter_result = enter_result
    def __enter__(self):
        return self.enter_result
    def __exit__(self, *excinfo):
        pass


def create_pipeline(token: str, device: str | None = None) -> Any:
    """
    Crea y devuelve un pipeline de diarización.

    Args:
        token: Token de acceso de Hugging Face
        device: Dispositivo para inferencia ('cuda', 'cpu', o None para auto)

    Returns:
        Pipeline configurado para diarización
    """
    Pipeline = lazy_load("pyannote.audio", "Pipeline")
    torch = lazy_load("torch", "")
    pipeline = Pipeline.from_pretrained(
        DEFAULT_DIARIZATION_MODEL,
        use_auth_token=token
    )
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    pipeline.to(torch.device(device))
    return pipeline


def create_embedding_pipeline(token: str, device: str | None = None) -> Any:
    """
    Crea y devuelve un pipeline de extracción de embeddings de speaker.

    Args:
        token: Token de acceso de Hugging Face
        device: Dispositivo para inferencia ('cuda', 'cpu', o None para auto)

    Returns:
        Pipeline configurado para embeddings
    """
    # Importar desde el submódulo correcto
    SpeakerEmbedding = lazy_load("pyannote.audio.pipelines.speaker_embedding", "SpeakerEmbedding")
    torch = lazy_load("torch", "")
    embedder = SpeakerEmbedding.from_pretrained(
        EMBEDDING_MODEL,
        use_auth_token=token
    )
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    embedder.to(torch.device(device))
    return embedder


def perform_diarization(
    pipeline: Any,
    audio_data: Dict[str, Any],
    num_speakers: int | None = None,
    progress_hook: Any | None = None,
    hf_token: str = ""
) -> DiarizationResult:
    """
    Realiza la diarización y extracción de embeddings en los datos de audio.

    Args:
        pipeline: Pipeline de diarización configurado
        audio_data: Datos de audio (waveform, sample_rate)
        num_speakers: Número de locutores (opcional)
        progress_hook: Callback de progreso (opcional)
        hf_token: Token de HF para el pipeline de embeddings

    Returns:
        Resultado de diarización con métricas y embeddings por segmento
    """
    # Preparar args
    args = {"num_speakers": num_speakers} if num_speakers else {}

    # ProgressHook
    if progress_hook is None:
        Hook = lazy_load("pyannote.audio.pipelines.utils.hook", "ProgressHook")
        hook = Hook()
    else:
        hook = progress_hook

    # Ejecutar diarización
    start_time = time.time()
    ctx = hook if hasattr(hook, "__enter__") else nullcontext(hook)
    with ctx as h:
        diarization = pipeline(audio_data, hook=h, **args)
    processing_time = time.time() - start_time

    audio_duration = audio_data["waveform"].shape[1] / audio_data["sample_rate"]
    speed_factor = audio_duration / processing_time if processing_time else float('inf')

    logger.info(
        "Diarización: %.2fs audio, %.2fs proceso (×%.2f)",
        audio_duration, processing_time, speed_factor
    )

    # Extraer embeddings siempre
    embedder = create_embedding_pipeline(hf_token)
    segments: List[Tuple[Any, str, List[float]]] = []
    for segment, _, speaker in diarization.itertracks(yield_label=True):
        emb_tensor = embedder.crop_and_embed(audio_data, segment)
        emb = emb_tensor.cpu().numpy().flatten().tolist()
        segments.append((segment, speaker, emb))

    return DiarizationResult(
        diarization=diarization,
        audio_duration=audio_duration,
        processing_time=processing_time,
        speed_factor=speed_factor,
        segments=segments
    )


def format_diarization_result(
    audio_path: str,
    result: DiarizationResult
) -> DiarizationInfo:
    """
    Formatea la información de diarización para JSON.

    Args:
        audio_path: Ruta al archivo (solo para clave de embedding)
        result: Resultado de diarización

    Returns:
        Dict con métricas y lista de segmentos con embeddings
    """
    metrics: DiarizationMetrics = {
        "audio_duration": round(result.audio_duration, 2),
        "processing_time": round(result.processing_time, 2),
        "speed_factor": round(result.speed_factor, 2)
    }

    speakers: List[SpeakerSegment] = []
    for segment, speaker, emb in result.segments:
        speakers.append({
            "start": segment.start,
            "end": segment.end,
            "speaker": speaker,
            "embedding": emb
        })

    return {"metrics": metrics, "speakers": speakers}
