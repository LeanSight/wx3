"""input_media.py
Utilidades de carga de audio / video con torchaudio y PyAV.

Provee una única función pública:

    load_media(path: str | Path,
               device: str | None = None,
               target_sr: int = DEFAULT_SR,
               use_cache: bool = True) -> AudioData

que devuelve un diccionario con:

    {
        "waveform": torch.Tensor,   # [1, n_samples]  – mono, float32 ∈ [-1, 1]
        "sample_rate": int          # == target_sr
    }

El módulo mantiene la interfaz previa para los consumidores de wx3,
pero corrige inconsistencias de frecuencia de muestreo, fallos con
contenedores multistream y dependencias opcionales de Torch.

Incluye sistema de caché para evitar cargar múltiples veces el mismo archivo.

© 2025 — Licencia MIT
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, TypedDict, Union, Optional, Dict, Tuple

from lazy_loading import lazy_load
from constants import AUDIO_EXTENSIONS, VIDEO_EXTENSIONS

logger = logging.getLogger("input_media")

# ──────────────────────────────────────────────
# Tipado
# ──────────────────────────────────────────────


class AudioData(TypedDict):
    """Estructura de datos estándar para audio cargado."""
    waveform: Any  # torch.Tensor en tiempo de ejecución
    sample_rate: int


# ──────────────────────────────────────────────
# Constantes
# ──────────────────────────────────────────────

DEFAULT_SR: int = 16_000

# Configuración de caché
_MAX_CACHE_SIZE_BYTES: int = 2 * 1024 * 1024 * 1024  # 2GB por defecto
_MAX_CACHE_ENTRIES: int = 20  # Número máximo de archivos en caché

# ──────────────────────────────────────────────
# Sistema de caché
# ──────────────────────────────────────────────

# Caché global con clave compuesta (ruta + dispositivo)
_audio_cache: Dict[Tuple[Path, str], Dict[str, Any]] = {}
_cache_size_bytes: int = 0
_cache_access_order: list[Tuple[Path, str]] = []  # Para implementar política LRU


def set_max_cache_size(size_bytes: int) -> None:
    """Configura el tamaño máximo de caché de audio en bytes."""
    global _MAX_CACHE_SIZE_BYTES
    _MAX_CACHE_SIZE_BYTES = size_bytes
    logger.info(f"Tamaño máximo de caché configurado a {size_bytes/1024/1024:.1f}MB")
    _trim_cache_if_needed()


def set_max_cache_entries(max_entries: int) -> None:
    """Configura el número máximo de entradas en la caché."""
    global _MAX_CACHE_ENTRIES
    _MAX_CACHE_ENTRIES = max_entries
    logger.info(f"Número máximo de entradas en caché configurado a {max_entries}")
    _trim_cache_if_needed()


def clear_audio_cache() -> None:
    """Limpia la caché de audio completamente."""
    global _audio_cache, _cache_size_bytes, _cache_access_order
    _audio_cache.clear()
    _cache_access_order = []
    _cache_size_bytes = 0
    logger.info("Caché de audio limpiada")


def get_cache_info() -> Dict[str, Any]:
    """Devuelve información sobre el estado actual de la caché."""
    return {
        "entries": len(_audio_cache),
        "size_bytes": _cache_size_bytes,
        "size_mb": _cache_size_bytes / 1024 / 1024,
        "max_size_bytes": _MAX_CACHE_SIZE_BYTES,
        "max_size_mb": _MAX_CACHE_SIZE_BYTES / 1024 / 1024,
        "max_entries": _MAX_CACHE_ENTRIES,
        "usage_percent": (_cache_size_bytes / _MAX_CACHE_SIZE_BYTES) * 100 if _MAX_CACHE_SIZE_BYTES > 0 else 0,
        "cached_files": [str(path) for path, _ in _audio_cache.keys()]
    }


def _update_cache_access(cache_key: Tuple[Path, str]) -> None:
    """Actualiza el orden de acceso para la política LRU."""
    global _cache_access_order
    
    # Eliminar clave si ya está en la lista
    if cache_key in _cache_access_order:
        _cache_access_order.remove(cache_key)
    
    # Añadir clave al final (más recientemente usada)
    _cache_access_order.append(cache_key)


def _estimate_tensor_size(tensor: Any) -> int:
    """Estima el tamaño en bytes de un tensor."""
    torch = lazy_load("torch", "")
    
    if not isinstance(tensor, torch.Tensor):
        # Si no es un tensor, devolver una estimación conservadora
        return 1024 * 1024  # 1MB
    
    # Calcular tamaño basado en el tipo de datos y número de elementos
    return tensor.element_size() * tensor.nelement()


def _trim_cache_if_needed() -> None:
    """
    Reduce el tamaño de la caché si excede los límites configurados.
    Utiliza una política LRU (Least Recently Used).
    """
    global _audio_cache, _cache_size_bytes, _cache_access_order
    
    # Verificar límite de entradas
    while len(_audio_cache) > _MAX_CACHE_ENTRIES and _cache_access_order:
        # Eliminar la entrada menos recientemente usada
        oldest_key = _cache_access_order.pop(0)
        if oldest_key in _audio_cache:
            # Estimar tamaño antes de eliminar
            waveform = _audio_cache[oldest_key]["waveform"]
            approx_size = _estimate_tensor_size(waveform)
            
            # Eliminar de la caché
            del _audio_cache[oldest_key]
            _cache_size_bytes = max(0, _cache_size_bytes - approx_size)
            
            logger.debug(
                f"Entrada eliminada de caché por límite de entradas: "
                f"{oldest_key[0].name} ({approx_size/1024/1024:.1f}MB)"
            )
    
    # Verificar límite de tamaño
    while _cache_size_bytes > _MAX_CACHE_SIZE_BYTES and _cache_access_order:
        # Eliminar la entrada menos recientemente usada
        oldest_key = _cache_access_order.pop(0)
        if oldest_key in _audio_cache:
            # Estimar tamaño antes de eliminar
            waveform = _audio_cache[oldest_key]["waveform"]
            approx_size = _estimate_tensor_size(waveform)
            
            # Eliminar de la caché
            del _audio_cache[oldest_key]
            _cache_size_bytes = max(0, _cache_size_bytes - approx_size)
            
            logger.debug(
                f"Entrada eliminada de caché por límite de tamaño: "
                f"{oldest_key[0].name} ({approx_size/1024/1024:.1f}MB)"
            )


# ──────────────────────────────────────────────
# API pública
# ──────────────────────────────────────────────


def get_supported_extensions() -> dict[str, list[str]]:
    """Devuelve las extensiones de audio y video aceptadas."""
    return {"audio": AUDIO_EXTENSIONS, "video": VIDEO_EXTENSIONS}


def get_optimal_device() -> str:
    """
    Determina el mejor dispositivo disponible.

    Retorna "cuda" si Torch está instalado y hay GPU disponible,
    de lo contrario "cpu". Nunca lanza ImportError.
    """
    try:
        import torch  # noqa: WPS433  – import dinámico controlado
        return "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        logger.warning("torch no está instalado; usando CPU")
        return "cpu"


def load_media(
    input_path: Union[str, Path],
    device: Optional[str] = None,
    target_sr: int = DEFAULT_SR,
    use_cache: bool = True,
) -> AudioData:
    """
    Carga audio desde un archivo de audio *o* video, opcionalmente usando caché.

    Args:
        input_path: Ruta al archivo multimedia.
        device: "cpu" | "cuda" | None → se autocontrola.
        target_sr: Frecuencia de muestreo de salida (Hz).
        use_cache: Si se debe usar el sistema de caché.

    Returns:
        AudioData dict con waveform mono y sample_rate == target_sr.
    """
    input_path = Path(input_path).resolve()
    logger.info("Procesando archivo multimedia: %s", input_path)

    # Selección de dispositivo
    if device is None:
        device = get_optimal_device()

    # Clave de caché compuesta por ruta + dispositivo
    cache_key = (input_path, device)
    
    # Verificar caché si está habilitada
    if use_cache and cache_key in _audio_cache:
        logger.info(f"Usando audio cacheado para {input_path.name}")
        # Actualizar orden de acceso LRU
        _update_cache_access(cache_key)
        return _audio_cache[cache_key]

    # Determinar tipo de archivo
    suffix = input_path.suffix.lower()
    audio_exts, video_exts = set(AUDIO_EXTENSIONS), set(VIDEO_EXTENSIONS)

    file_type = (
        "audio"
        if suffix in audio_exts
        else "video"
        if suffix in video_exts
        else "desconocido"
    )
    logger.info("Tipo de archivo detectado: %s", file_type)

    # Cargar audio según el tipo de archivo y extensión
    if file_type == "audio" and _can_use_torchaudio(suffix):
        audio_data = _load_with_torchaudio(input_path, device, target_sr)
    else:
        # fallback general
        audio_data = _load_with_pyav(input_path, device, target_sr)
    
    # Cachear si se solicita
    if use_cache:
        # Estimar tamaño (waveform es un tensor)
        waveform = audio_data["waveform"]
        approx_size = _estimate_tensor_size(waveform)
        
        # Añadir a la caché
        _audio_cache[cache_key] = audio_data
        global _cache_size_bytes
        _cache_size_bytes += approx_size
        
        # Actualizar orden de acceso LRU
        _update_cache_access(cache_key)
        
        logger.debug(
            f"Audio cacheado: {input_path.name} "
            f"({approx_size/1024/1024:.1f}MB)"
        )
        
        # Verificar y ajustar caché si es necesario
        _trim_cache_if_needed()
    
    return audio_data


# ──────────────────────────────────────────────
# Implementación interna
# ──────────────────────────────────────────────


def _can_use_torchaudio(extension: str) -> bool:
    """Determina si torchaudio puede manejar nativamente la extensión."""
    return extension in {".wav", ".mp3", ".flac", ".ogg"}


def _load_with_torchaudio(
    path: Path,
    device: str,
    target_sr: int,
) -> AudioData:
    """Carga audio con torchaudio, re‑muestreando a `target_sr` si es preciso."""
    torchaudio = lazy_load("torchaudio", "")
    torch = lazy_load("torch", "")

    logger.info("Cargando audio con torchaudio: %s", path)
    waveform, sample_rate = torchaudio.load(str(path))

    # Forzar mono
    if waveform.shape[0] > 1:
        logger.info("Convirtiendo de %d canales a mono", waveform.shape[0])
        waveform = torch.mean(waveform, dim=0, keepdim=True)

    # Resampleo coherente
    if sample_rate != target_sr:
        logger.info("Resampleando de %d → %d Hz", sample_rate, target_sr)
        resample = torchaudio.transforms.Resample(orig_freq=sample_rate, new_freq=target_sr)
        waveform = resample(waveform)
        sample_rate = target_sr

    waveform = waveform.to(device)
    duration = waveform.shape[1] / sample_rate
    logger.info("Audio cargado: %.2f s – device=%s", duration, device)

    return {"waveform": waveform, "sample_rate": sample_rate}


def _load_with_pyav(
    path: Path,
    device: str,
    target_sr: int,
) -> AudioData:
    """
    Extrae y re‑muestrea audio con PyAV, manejando correctamente
    el caso en que `resample()` devuelve una lista de frames,
    concatenando en el eje temporal y garantizando un tensor (C, T).
    """
    av    = lazy_load("av", "")
    torch = lazy_load("torch", "")
    np    = lazy_load("numpy", "")

    logger.info("Procesando con PyAV: %s", path)
    try:
        with av.open(str(path)) as container:
            stream = next((s for s in container.streams if s.type == "audio"), None)
            if stream is None:
                raise ValueError(f"Sin pista de audio en {path}")

            resampler = av.AudioResampler(format="s16", layout="mono", rate=target_sr)

            audio_parts: list[np.ndarray] = []
            for frame in container.decode(stream):
                resampled = resampler.resample(frame)
                frames = resampled if isinstance(resampled, list) else [resampled]
                for rframe in frames:
                    arr = rframe.to_ndarray()
                    # Si viene 1D, pasar a (1, N)
                    if arr.ndim == 1:
                        arr = arr[np.newaxis, :]
                    audio_parts.append(arr)

            if not audio_parts:
                raise RuntimeError("No se extrajeron frames de audio.")

            # Concatenar a lo largo del tiempo → eje 1
            audio_np = np.concatenate(audio_parts, axis=1)

    except Exception as exc:
        logger.error("Error al decodificar con PyAV: %s", exc)
        raise

    # Convertir a tensor y normalizar
    waveform = torch.from_numpy(audio_np).float().div_(32768.0).to(device)

    # Asegurar forma (channels, time)
    if waveform.ndim == 1:
        waveform = waveform.unsqueeze(0)

    duration = waveform.shape[1] / target_sr
    logger.info("Audio extraído: %.2f s – device=%s", duration, device)

    return {"waveform": waveform, "sample_rate": target_sr}