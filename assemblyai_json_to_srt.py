"""
Conversión de JSON de AssemblyAI a SRT usando la lógica de sentence_grouping.

Refactorizado para reutilizar la lógica de agrupación de WX3.
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from constants import GroupingMode
from sentence_grouping import group_chunks_by_sentences, group_chunks_by_speaker_only
from output_formatters import format_timestamp


def ms_to_seconds(milliseconds: int) -> float:
    """Convierte milisegundos a segundos."""
    return milliseconds / 1000.0


def assemblyai_words_to_wx3_chunks(words: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Convierte palabras de AssemblyAI a chunks de WX3.
    
    AssemblyAI format:
        [{'text': 'word', 'start': 0, 'end': 500, 'speaker': 'A'}, ...]
    
    WX3 format:
        [{'text': 'word', 'timestamp': (0.0, 0.5), 'speaker': 'SPEAKER_00'}, ...]
    
    Args:
        words: Lista de palabras en formato AssemblyAI
        
    Returns:
        Lista de chunks en formato WX3
    """
    chunks = []
    for word in words:
        chunk = {
            'text': word['text'],
            'timestamp': (ms_to_seconds(word['start']), ms_to_seconds(word['end'])),
            'speaker': word.get('speaker', 'UNKNOWN')
        }
        chunks.append(chunk)
    return chunks


def wx3_chunks_to_srt(
    chunks: List[Dict[str, Any]],
    speaker_names: Optional[Dict[str, str]] = None
) -> str:
    """
    Convierte chunks de WX3 a formato SRT.
    
    Args:
        chunks: Lista de chunks en formato WX3
        speaker_names: Mapeo opcional de speakers (ej: {'A': 'Marcel'})
        
    Returns:
        String con contenido SRT
    """
    srt_lines = []
    
    for idx, chunk in enumerate(chunks, 1):
        text = chunk['text']
        timestamp = chunk['timestamp']
        speaker = chunk.get('speaker', '')
        
        # Aplicar mapeo de nombres si existe
        if speaker_names and speaker in speaker_names:
            speaker = speaker_names[speaker]
        
        # Formatear timestamps (SRT usa coma como separador)
        start_time = format_timestamp(timestamp[0], separator=',')
        end_time = format_timestamp(timestamp[1], separator=',')
        
        # Formatear texto con speaker
        if speaker:
            formatted_text = f"[{speaker}] {text}"
        else:
            formatted_text = text
        
        # Agregar entrada SRT
        srt_lines.append(f"{idx}")
        srt_lines.append(f"{start_time} --> {end_time}")
        srt_lines.append(formatted_text)
        srt_lines.append("")  # Línea vacía entre entradas
    
    return "\n".join(srt_lines)


def words_to_srt(
    words: List[Dict[str, Any]],
    speaker_names: Optional[Dict[str, str]] = None,
    output_file: Optional[str] = None,
    mode: str = "sentences",
    max_chars: int = 80,
    max_duration_ms: int = 10000
) -> str:
    """
    Convierte palabras de AssemblyAI a formato SRT.
    
    Args:
        words: Lista de palabras con timestamps de AssemblyAI
        speaker_names: Mapeo opcional de speakers
        output_file: Ruta del archivo de salida (opcional)
        mode: Modo de agrupación ('sentences' o 'speaker-only')
        max_chars: Máximo de caracteres por segmento
        max_duration_ms: Máxima duración en milisegundos por segmento
        
    Returns:
        Contenido SRT como string
    """
    # Convertir formato AssemblyAI a formato WX3
    wx3_chunks = assemblyai_words_to_wx3_chunks(words)
    
    # Aplicar agrupación según el modo
    max_duration_s = max_duration_ms / 1000.0
    
    if mode == "sentences" or mode == GroupingMode.sentences:
        grouped_chunks = group_chunks_by_sentences(
            wx3_chunks,
            max_chars=max_chars,
            max_duration_s=max_duration_s
        )
    elif mode == "speaker-only" or mode == GroupingMode.speaker_only:
        grouped_chunks = group_chunks_by_speaker_only(wx3_chunks)
    else:
        raise ValueError(f"Modo inválido: {mode}. Use 'sentences' o 'speaker-only'")
    
    # Convertir a SRT
    srt_content = wx3_chunks_to_srt(grouped_chunks, speaker_names)
    
    # Guardar si se especificó archivo de salida
    if output_file:
        output_path = Path(output_file)
        output_path.write_text(srt_content, encoding='utf-8')
    
    return srt_content



