"""alignment.py
Funciones utilitarias para la fusión de información de diarización y transcripción.
Incluye:
- align_diarization_with_transcription: asigna locutor a cada chunk
- slice_audio: recorta waveform con padding
- group_turns_by_speaker: agrupa turnos contiguos del mismo locutor
"""
from itertools import groupby
from typing import Any, Dict, List, Iterable

__all__ = [
    "align_diarization_with_transcription",
    "slice_audio",
    "group_turns_by_speaker",
]


def align_diarization_with_transcription(
    diar_segments: List[Dict[str, Any]],
    transcript_chunks: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Alinea cada chunk de transcripción con el locutor más probable.

    Estrategia:
    1. Si los chunks ya traen ``speaker`` se devuelven sin modificar.
    2. Si no, se usa un índice deslizante O(n + m) basado en el punto medio.
    """
    if not diar_segments or not transcript_chunks:
        return []

    # chunks ya alineados
    if "speaker" in transcript_chunks[0]:
        return transcript_chunks

    diar_sorted = sorted(diar_segments, key=lambda seg: seg["start"])
    aligned: List[Dict[str, Any]] = []
    diar_idx = 0

    for chunk in transcript_chunks:
        ts_start, ts_end = chunk["timestamp"]
        if ts_start is None or ts_end is None:
            continue
        midpoint = (ts_start + ts_end) / 2
        while diar_idx < len(diar_sorted) - 1 and diar_sorted[diar_idx]["end"] < midpoint:
            diar_idx += 1
        aligned.append({**chunk, "speaker": diar_sorted[diar_idx]["speaker"]})

    return aligned


def slice_audio(
    audio: Dict[str, Any],
    segment_start_s: float,
    segment_end_s: float,
    padding_s: float = 0.25,
) -> Dict[str, Any]:
    """Recorta ``audio`` aplicando un padding opcional.

    Args:
        audio: Dict con ``waveform`` (Tensor) y ``sample_rate`` (int).
        segment_start_s: Inicio del segmento (s).
        segment_end_s: Fin del segmento (s).
        padding_s: Margen añadido en ambos extremos.
    """
    waveform = audio["waveform"]
    sample_rate = audio["sample_rate"]

    first_idx = max(0, int((segment_start_s - padding_s) * sample_rate))
    last_idx = min(waveform.shape[1], int((segment_end_s + padding_s) * sample_rate))

    return {
        "waveform": waveform[:, first_idx:last_idx],
        "sample_rate": sample_rate,
    }


def group_turns_by_speaker(
    turns: Iterable[Dict[str, Any]],
    max_gap_s: float = 0.3,
) -> List[Dict[str, Any]]:
    grouped: List[Dict[str, Any]] = []
    sorted_turns = sorted(turns, key=lambda t: (t["speaker"], t["start"]))

    for speaker, segs_iter in groupby(sorted_turns, key=lambda t: t["speaker"]):
        segs = list(segs_iter)
        current_start, current_end = segs[0]["start"], segs[0]["end"]

        for seg in segs[1:]:
            if seg["start"] - current_end <= max_gap_s:
                current_end = seg["end"]
            else:
                grouped.append({"start": current_start, "end": current_end, "speaker": speaker})
                current_start, current_end = seg["start"], seg["end"]

        grouped.append({"start": current_start, "end": current_end, "speaker": speaker})

    return sorted(grouped, key=lambda t: t["start"])


from typing import List, Dict
import logging

def log_first_all_speakers_participation(chunks: List[Dict], logger: logging.Logger) -> None:
    """
    Registra en el log el primer segmento en el que todos los hablantes han participado
    al menos una vez, basado en la información de los chunks alineados.

    Args:
        chunks (List[Dict]): Lista de segmentos con timestamp y etiqueta de hablante.
        logger (logging.Logger): Logger configurado para la aplicación.
    """
    all_speakers = {chunk["speaker"] for chunk in chunks if "speaker" in chunk}
    seen_speakers = set()

    for chunk in chunks:
        speaker = chunk.get("speaker")
        if speaker:
            seen_speakers.add(speaker)

        if seen_speakers == all_speakers:
            t_start, t_end = chunk["timestamp"]
            logger.info(
                f"🗣️ Todos los hablantes participaron hasta {t_end:.2f}s "
                f"(primer segmento: {t_start:.2f}s → {t_end:.2f}s)"
            )
            return

from typing import List, Dict

def apply_speaker_names(chunks: List[Dict], speaker_names: List[str]) -> None:
    """
    Reemplaza los nombres de los hablantes genéricos (SPEAKER_00, SPEAKER_01...) 
    por nombres personalizados en los chunks modificando en sitio.

    Args:
        chunks: Lista de diccionarios con clave 'speaker'.
        speaker_names: Lista de nombres personalizados.
    """
    for chunk in chunks:
        speaker = chunk.get("speaker")
        if speaker and speaker.startswith("SPEAKER_"):
            idx = int(speaker.replace("SPEAKER_", ""))
            if idx < len(speaker_names):
                chunk["speaker"] = speaker_names[idx]
