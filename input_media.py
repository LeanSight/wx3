"""input_media.py
Utilidades de carga de audio / video con torchaudio y PyAV.

Provee una única función pública:

    load_media(path: str | Path,
               device: str | None = None,
               target_sr: int = DEFAULT_SR) -> AudioData

que devuelve un diccionario con:

    {
        "waveform": torch.Tensor,   # [1, n_samples]  – mono, float32 ∈ [-1, 1]
        "sample_rate": int          # == target_sr
    }

El módulo mantiene la interfaz previa para los consumidores de wx3,
pero corrige inconsistencias de frecuencia de muestreo, fallos con
contenedores multistream y dependencias opcionales de Torch.

© 2025 — Licencia MIT
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, TypedDict, Union, Optional

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
        import torch  # noqa: WPS433  – import dinámico controlado
        return "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        logger.warning("torch no está instalado; usando CPU")
        return "cpu"


def load_media(
    input_path: Union[str, Path],
    device: Optional[str] = None,
    target_sr: int = DEFAULT_SR,
) -> AudioData:
    """
    Carga audio desde un archivo de audio *o* video.

    Args:
        input_path: Ruta al archivo multimedia.
        device: "cpu" | "cuda" | None → se autocontrola.
        target_sr: Frecuencia de muestreo de salida (Hz).

    Returns:
        AudioData dict con waveform mono y sample_rate == target_sr.
    """
    input_path = Path(input_path)
    logger.info("Procesando archivo multimedia: %s", input_path)

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

    # Selección de dispositivo
    if device is None:
        device = get_optimal_device()

    if file_type == "audio" and _can_use_torchaudio(suffix):
        return _load_with_torchaudio(input_path, device, target_sr)

    # fallback general
    return _load_with_pyav(input_path, device, target_sr)


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
        logger.info("Resampleando de %d → %d Hz", sample_rate, target_sr)
        resample = torchaudio.transforms.Resample(orig_freq=sample_rate, new_freq=target_sr)
        waveform = resample(waveform)
        sample_rate = target_sr

    waveform = waveform.to(device)
    duration = waveform.shape[1] / sample_rate
    logger.info("Audio cargado: %.2f s – device=%s", duration, device)

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
    logger.info("Audio extraído: %.2f s – device=%s", duration, device)

    return {"waveform": waveform, "sample_rate": target_sr}



