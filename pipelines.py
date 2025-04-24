"""
Módulo centralizado para la creación y cacheado de pipelines.

Proporciona funciones cacheadas para crear pipelines de transcripción
y diarización, evitando la recreación redundante de modelos.
"""

import logging
import time
from functools import lru_cache
from typing import Any, Optional

from constants import (
    DEFAULT_ATTN_TYPE, DEFAULT_MODEL, DEFAULT_DIARIZATION_MODEL,
    LOG_INIT_TRANSCRIPTION, LOG_INIT_DIARIZATION
)
from lazy_loading import lazy_load

# Logger específico para pipelines
logger = logging.getLogger("wx3.pipelines")


@lru_cache(maxsize=2)
def get_transcription_pipeline(
    model_name: str = DEFAULT_MODEL,
    device: Optional[str] = None,
    attn_type: str = DEFAULT_ATTN_TYPE
) -> Any:
    """
    Obtiene o crea un pipeline de transcripción cacheado.
    
    Args:
        model_name: Nombre del modelo de Whisper a utilizar
        device: Dispositivo para inferencia ('cuda', 'cpu', o None para auto)
        attn_type: Tipo de atención a utilizar ('sdpa', 'eager', 'flash')
        
    Returns:
        Pipeline configurado para transcripción
    
    Notes:
        Esta función utiliza lru_cache para evitar la carga repetida de modelos.
        El tamaño de caché es 2 para permitir comparar dos modelos distintos.
    """
    start_time = time.time()
    
    # Importación local para evitar dependencias pesadas en importación
    from transcription import create_pipeline
    
    # Registrar información
    logger.info(LOG_INIT_TRANSCRIPTION, model_name, device or "auto")
    
    # Crear pipeline a través de la función original
    pipeline = create_pipeline(model_name, device, attn_type)
    
    # Registrar tiempo de carga
    elapsed = time.time() - start_time
    logger.info(f"Pipeline de transcripción creado en {elapsed:.2f}s")
    
    return pipeline


@lru_cache(maxsize=1)
def get_diarization_pipeline(
    token: str,
    device: Optional[str] = None
) -> Any:
    """
    Obtiene o crea un pipeline de diarización cacheado.
    
    Args:
        token: Token de acceso de Hugging Face
        device: Dispositivo para inferencia ('cuda', 'cpu', o None para auto)
        
    Returns:
        Pipeline configurado para diarización
    
    Notes:
        Esta función utiliza lru_cache para evitar la carga repetida de modelos.
        El tamaño de caché es 1 ya que generalmente solo se usa un modelo de diarización.
    """
    start_time = time.time()
    
    # Importación local para evitar dependencias pesadas en importación
    from diarization import create_pipeline
    
    # Registrar información
    logger.info(LOG_INIT_DIARIZATION, device or "auto")
    
    # Crear pipeline a través de la función original
    pipeline = create_pipeline(token, device)
    
    # Registrar tiempo de carga
    elapsed = time.time() - start_time
    logger.info(f"Pipeline de diarización creado en {elapsed:.2f}s")
    
    return pipeline


def clear_pipeline_cache() -> None:
    """
    Limpia la caché de pipelines para liberar memoria.
    
    Esta función es útil cuando se necesita liberar recursos
    o cuando se desea forzar la recarga de modelos.
    """
    get_transcription_pipeline.cache_clear()
    get_diarization_pipeline.cache_clear()
    logger.info("Caché de pipelines limpiada")


# Información sobre caché para diagnóstico
def get_pipeline_cache_info() -> dict:
    """
    Devuelve información sobre el estado de la caché de pipelines.
    
    Returns:
        Diccionario con información de caché para cada tipo de pipeline
    """
    return {
        "transcription": {
            "hits": get_transcription_pipeline.cache_info().hits,
            "misses": get_transcription_pipeline.cache_info().misses,
            "maxsize": get_transcription_pipeline.cache_info().maxsize,
            "currsize": get_transcription_pipeline.cache_info().currsize,
        },
        "diarization": {
            "hits": get_diarization_pipeline.cache_info().hits,
            "misses": get_diarization_pipeline.cache_info().misses,
            "maxsize": get_diarization_pipeline.cache_info().maxsize,
            "currsize": get_diarization_pipeline.cache_info().currsize,
        }
    }