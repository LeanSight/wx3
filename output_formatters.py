from datetime import timedelta
from pathlib import Path
from typing import Any, Optional, List, Dict

from constants import SubtitleFormat

def format_timestamp(seconds: float, separator: str = ",") -> str:
    """
    Formatea un tiempo en segundos a formato de subtítulos HH:MM:SS,MMM.
    
    Args:
        seconds: Tiempo en segundos a formatear
        separator: Separador entre segundos y milisegundos (coma para SRT, punto para VTT)
    
    Returns:
        String formateado como HH:MM:SS{separator}MMM
    """
    time_delta = timedelta(seconds=float(seconds))
    total_seconds = int(time_delta.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds_part = divmod(remainder, 60)
    milliseconds = int(time_delta.microseconds / 1000)
    
    return f"{hours:02}:{minutes:02}:{seconds_part:02}{separator}{milliseconds:03}"

def save_json(output_path: Path, data: Any) -> None:
    """
    Guarda datos en formato JSON.
    
    Args:
        output_path: Ruta donde guardar el archivo (se añadirá extensión .json)
        data: Datos a guardar en formato JSON
    """
    final_path = output_path.with_suffix(".json")
    import json

    with open(final_path, "w", encoding="utf-8") as output_file:
        json.dump(data, output_file, ensure_ascii=False, indent=2)

def save_subtitles(
    transcription_result,
    output_file_path: str | Path,
    format_type: str,
    *,
    with_speaker: bool = False,
    chunks: Optional[List[Dict[str, Any]]] = None,
) -> None:
    """
    Guarda transcripción en formatos de subtítulos (SRT, VTT) o texto plano.
    
    Args:
        transcription_result: Resultado de transcripción
        output_file_path: Ruta donde guardar el archivo
        format_type: Formato de salida ('srt', 'vtt', 'txt')
        with_speaker: Si debe incluir información del hablante
        chunks: Segmentos personalizados (si es None, usa transcription_result.chunks)
    """
    try:
        subtitle_format = SubtitleFormat.from_string(format_type)
    except ValueError:
        raise ValueError(f"Formato no soportado: {format_type}")
    
    output_path = Path(output_file_path)
    text_segments = chunks if chunks is not None else transcription_result.chunks

    # Usar pattern matching para procesar según el formato
    match subtitle_format:
        case SubtitleFormat.TXT:
            _save_as_text(text_segments, output_path, with_speaker)
        
        case SubtitleFormat.SRT | SubtitleFormat.VTT:
            _save_as_subtitles(text_segments, output_path, subtitle_format, with_speaker)
        
        case _:
            raise ValueError(f"Formato no implementado: {subtitle_format}")

def _save_as_text(
    segments: List[Dict[str, Any]],
    output_path: Path,
    with_speaker: bool
) -> None:
    """Guarda segmentos como texto plano."""
    text_lines = [
        f"{segment.get('speaker', '').strip() + ': ' if with_speaker and 'speaker' in segment else ''}{segment['text'].strip()}"
        for segment in segments
        if segment["text"].strip()
    ]
    output_path.write_text("\n".join(text_lines), encoding="utf-8")

def _save_as_subtitles(
    segments: List[Dict[str, Any]],
    output_path: Path,
    format_type: SubtitleFormat,
    with_speaker: bool
) -> None:
    """Guarda segmentos como subtítulos SRT o VTT."""
    subtitle_lines: List[str] = []
    
    # Encabezado específico para VTT
    if format_type == SubtitleFormat.VTT:
        subtitle_lines.append("WEBVTT\n")

    # Procesar cada segmento
    for segment_index, segment in enumerate(segments, 1):
        # Verificar si tenemos marcas de tiempo válidas
        timestamp = segment.get("timestamp", (None, None))
        if not isinstance(timestamp, tuple) or len(timestamp) != 2:
            continue
            
        start_time, end_time = timestamp
        if start_time is None or end_time is None:
            continue

        # Configurar formato según el tipo de subtítulo
        match format_type:
            case SubtitleFormat.SRT:
                time_separator = ","
                subtitle_lines.append(str(segment_index))
                subtitle_lines.append(f"{format_timestamp(start_time, time_separator)} --> {format_timestamp(end_time, time_separator)}")
            
            case SubtitleFormat.VTT:
                time_separator = "."
                subtitle_lines.append(f"{format_timestamp(start_time, time_separator)} --> {format_timestamp(end_time, time_separator)}")
        
        # Formatear el texto con el hablante si es necesario
        segment_text = segment["text"].strip()
        if with_speaker and "speaker" in segment:
            segment_text = f"{segment['speaker']}: {segment_text}"
            
        subtitle_lines.append(segment_text)
        subtitle_lines.append("")  # Línea en blanco entre subtítulos

    # Guardar el archivo de subtítulos
    output_path.write_text("\n".join(subtitle_lines), encoding="utf-8")