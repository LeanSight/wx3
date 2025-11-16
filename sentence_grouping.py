"""
Módulo para agrupar chunks de transcripción en segmentos más naturales.

Adaptado de la lógica de AssemblyAI para trabajar con chunks de Whisper
en lugar de palabras individuales.
"""

import re
from typing import Any, Dict, List, Optional


def is_sentence_end(text: str) -> bool:
    """
    Determina si un texto termina con un delimitador de oración.
    En español: . ! ? ; (y combinaciones con comillas o paréntesis)
    
    Args:
        text: Texto a analizar
        
    Returns:
        True si termina con delimitador de oración
    """
    text = text.rstrip()
    sentence_endings = r'[.!?;]["\'\)]*$'
    return bool(re.search(sentence_endings, text))


def is_strong_pause(text: str) -> bool:
    """
    Determina si hay una pausa fuerte (coma, dos puntos, etc.)
    
    Args:
        text: Texto a analizar
        
    Returns:
        True si termina con marca de pausa fuerte
    """
    text = text.rstrip()
    pause_marks = r'[,:]["\'\)]*$'
    return bool(re.search(pause_marks, text))


def group_chunks_by_sentences(
    chunks: List[Dict[str, Any]],
    max_chars: int = 80,
    max_duration_s: float = 10.0
) -> List[Dict[str, Any]]:
    """
    Agrupa chunks de transcripción en segmentos basados en oraciones completas.
    
    Prioridades de segmentación:
    1. Cambio de speaker (siempre crea nuevo segmento)
    2. Fin de oración (. ! ? ;)
    3. Pausa fuerte (,) si excede max_chars o max_duration
    4. Límites absolutos de max_chars o max_duration
    
    Args:
        chunks: Lista de chunks con 'text', 'timestamp', y opcionalmente 'speaker'
        max_chars: Máximo de caracteres por segmento
        max_duration_s: Máxima duración en segundos por segmento
        
    Returns:
        Lista de segmentos agrupados con 'text', 'timestamp', y 'speaker'
    """
    if not chunks:
        return []
    
    segments = []
    current_segment = _create_empty_segment(chunks[0].get('speaker'))
    
    for chunk in chunks:
        # Validar y extraer información del chunk
        chunk_info = _extract_chunk_info(chunk)
        if chunk_info is None:
            continue
        
        chunk_text, chunk_start, chunk_end, chunk_speaker = chunk_info
        
        # PRIORIDAD 1: Cambio de speaker
        if chunk_speaker and chunk_speaker != current_segment['speaker']:
            if current_segment['chunks']:
                _finalize_segment(current_segment, segments)
            
            current_segment = _create_empty_segment(chunk_speaker)
            current_segment['chunks'] = [chunk]
            current_segment['start'] = chunk_start
            current_segment['end'] = chunk_end
            continue
        
        # Calcular métricas temporales
        temp_text, duration = _calculate_segment_metrics(current_segment, chunk, chunk_end)
        
        # PRIORIDAD 2: Fin de oración
        if is_sentence_end(chunk_text):
            # Añadir el chunk actual al segmento
            if not current_segment['chunks']:
                current_segment['start'] = chunk_start
            current_segment['chunks'].append(chunk)
            current_segment['end'] = chunk_end
            
            # Finalizar el segmento
            _finalize_segment(current_segment, segments)
            
            # Reiniciar segmento
            current_segment = _create_empty_segment(chunk_speaker)
            continue
        
        # PRIORIDAD 3: Pausa fuerte + límites excedidos
        # Verificar si el segmento anterior terminó con pausa fuerte y ahora excedemos límites
        if current_segment['chunks'] and (len(temp_text) > max_chars or duration > max_duration_s):
            # Verificar si el último chunk del segmento actual termina con pausa fuerte
            last_chunk_text = current_segment['chunks'][-1]['text'].strip()
            if is_strong_pause(last_chunk_text):
                # Finalizar el segmento actual sin añadir el nuevo chunk
                _finalize_segment(current_segment, segments)
                
                current_segment = _create_empty_segment(chunk_speaker)
                current_segment['chunks'] = [chunk]
                current_segment['start'] = chunk_start
                current_segment['end'] = chunk_end
                continue
        
        # PRIORIDAD 4: Límites absolutos
        if len(temp_text) > max_chars * 1.5 or duration > max_duration_s * 1.5:
            if current_segment['chunks']:
                _finalize_segment(current_segment, segments)
            
            current_segment = _create_empty_segment(chunk_speaker)
            current_segment['chunks'] = [chunk]
            current_segment['start'] = chunk_start
            current_segment['end'] = chunk_end
            continue
        
        # Añadir chunk al segmento actual
        if not current_segment['chunks']:
            current_segment['start'] = chunk_start
        current_segment['chunks'].append(chunk)
        current_segment['end'] = chunk_end
    
    # Añadir el último segmento
    if current_segment['chunks']:
        _finalize_segment(current_segment, segments)
    
    return segments


def group_chunks_by_speaker_only(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Agrupa chunks en segmentos solo cuando cambia el speaker.
    Cada vez que cambia el hablante, se crea un nuevo segmento.
    
    Args:
        chunks: Lista de chunks con 'text', 'timestamp', y 'speaker'
        
    Returns:
        Lista de segmentos agrupados
    """
    if not chunks:
        return []
    
    segments = []
    current_segment = _create_empty_segment(chunks[0].get('speaker'))
    
    for chunk in chunks:
        # Validar y extraer información del chunk
        chunk_info = _extract_chunk_info(chunk)
        if chunk_info is None:
            continue
        
        chunk_text, chunk_start, chunk_end, chunk_speaker = chunk_info
        
        # Solo segmentar cuando cambia el speaker
        if chunk_speaker and chunk_speaker != current_segment['speaker']:
            # Guardar segmento actual
            if current_segment['chunks']:
                _finalize_segment(current_segment, segments)
            
            # Iniciar nuevo segmento
            current_segment = _create_empty_segment(chunk_speaker)
            current_segment['chunks'] = [chunk]
            current_segment['start'] = chunk_start
            current_segment['end'] = chunk_end
        else:
            # Continuar acumulando chunks del mismo speaker
            if not current_segment['chunks']:
                current_segment['start'] = chunk_start
            current_segment['chunks'].append(chunk)
            current_segment['end'] = chunk_end
    
    # Añadir el último segmento
    if current_segment['chunks']:
        _finalize_segment(current_segment, segments)
    
    return segments


def _create_empty_segment(speaker: Optional[str] = None) -> Dict[str, Any]:
    """
    Crea un segmento vacío.
    
    Args:
        speaker: Speaker inicial del segmento
        
    Returns:
        Diccionario con estructura de segmento vacío
    """
    return {
        'chunks': [],
        'speaker': speaker,
        'start': None,
        'end': None
    }


def _extract_chunk_info(chunk: Dict[str, Any]) -> Optional[tuple]:
    """
    Extrae y valida información de un chunk.
    
    Args:
        chunk: Chunk a procesar
        
    Returns:
        Tupla (text, start, end, speaker) o None si el chunk es inválido
    """
    chunk_text = chunk['text'].strip()
    if not chunk_text:
        return None
        
    timestamp = chunk.get('timestamp', (None, None))
    
    # Normalizar listas a tuplas (JSON serializa tuplas como listas)
    if isinstance(timestamp, list):
        timestamp = tuple(timestamp)
    
    if not isinstance(timestamp, tuple) or len(timestamp) != 2:
        return None
        
    chunk_start, chunk_end = timestamp
    if chunk_start is None or chunk_end is None:
        return None
    
    chunk_speaker = chunk.get('speaker')
    return (chunk_text, chunk_start, chunk_end, chunk_speaker)


def _calculate_segment_metrics(
    current_segment: Dict[str, Any],
    chunk: Dict[str, Any],
    chunk_end: float
) -> tuple:
    """
    Calcula métricas del segmento si se añade el chunk.
    
    Args:
        current_segment: Segmento actual
        chunk: Chunk a añadir
        chunk_end: Timestamp de fin del chunk
        
    Returns:
        Tupla (temp_text, duration)
    """
    temp_chunks = current_segment['chunks'] + [chunk]
    temp_text = ' '.join([c['text'].strip() for c in temp_chunks])
    
    if current_segment['start'] is not None:
        duration = chunk_end - current_segment['start']
    else:
        duration = 0
    
    return (temp_text, duration)


def _finalize_segment(current_segment: Dict[str, Any], segments: List[Dict[str, Any]]) -> None:
    """
    Finaliza un segmento y lo añade a la lista de segmentos.
    
    Args:
        current_segment: Segmento actual a finalizar
        segments: Lista de segmentos donde añadir
    """
    text = ' '.join([c['text'].strip() for c in current_segment['chunks']])
    segments.append({
        'text': text,
        'timestamp': (current_segment['start'], current_segment['end']),
        'speaker': current_segment['speaker']
    })
