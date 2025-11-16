"""
Módulo de procesamiento para wx3 que implementa la lógica principal
de diarización, transcripción y alineación.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from alignment import align_diarization_with_transcription, group_turns_by_speaker, slice_audio, apply_speaker_names
from constants import (
    DEFAULT_TASK, DEFAULT_LANGUAGE, DEFAULT_CHUNK_LENGTH, DEFAULT_BATCH_SIZE,
    LOG_DIARIZING, LOG_NUM_SPEAKERS, LOG_TRANSCRIBING, LOG_TASK, LOG_LANGUAGE, 
    LOG_SEGMENT_BATCH, MSG_SAVING_RESULTS, MSG_FILE_SAVED, MSG_UNKNOWN_FORMAT,
    GroupingMode
)
from diarization import (
    DiarizationResult,
    format_diarization_result,
    perform_diarization,
)
from input_media import load_media
from output_formatters import save_json, save_subtitles
from transcription import (
    TranscriptionResult,
    format_transcription_result,
    perform_transcription,
)


def prepare_diarization(
    file_path: Path,
    pipeline: Any,
    num_speakers: Optional[int],
    device_str: Optional[str],
    logger: logging.Logger,
    save_intermediate: bool = False,
    use_cache: bool = True
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Prepara los datos de diarización para un archivo.
    
    Args:
        file_path: Ruta al archivo de audio
        pipeline: Pipeline de diarización
        num_speakers: Número de hablantes (opcional)
        device_str: String del dispositivo
        logger: Instancia del logger
        save_intermediate: Si se deben guardar resultados intermedios
        use_cache: Si se debe usar el sistema de caché para audio
        
    Returns:
        Tupla de (segmentos de diarización, audio cargado)
    """
    logger.info(LOG_DIARIZING, file_path.name)
    logger.info(LOG_NUM_SPEAKERS, "Auto-detect" if num_speakers is None else num_speakers)
    
    # Realizar diarización
    diar_result, audio = diarize_file(
        audio_path=file_path,
        pipeline=pipeline,
        num_speakers=num_speakers,
        device=device_str,
        use_cache=use_cache
    )
    
    # Extraer segmentos del resultado
    diar_segments = format_diarization_result(diar_result)["speakers"]
    
    # Opcionalmente guardar resultado intermedio
    if save_intermediate:
        base_path = get_output_base_path(file_path, "process", "diarize", "intermediate")
        save_json(base_path, format_diarization_result(diar_result))
        logger.info(f"Diarización intermedia guardada: {base_path.with_suffix('.json').name}")
    
    return diar_segments, audio


def transcribe_by_speaker_turns(
    diar_segments: List[Dict[str, Any]],
    audio: Dict[str, Any],
    pipeline: Any,
    task_value: str,
    language: Optional[str],
    chunk_length: int,
    batch_size: int,
    logger: logging.Logger
) -> TranscriptionResult:
    """
    Transcribe audio procesando cada turno de hablante por separado.
    
    Args:
        diar_segments: Segmentos de diarización
        audio: Datos de audio
        pipeline: Pipeline de transcripción
        task_value: Valor de tarea (transcribe/translate)
        language: Código de idioma
        chunk_length: Longitud de chunk en segundos
        batch_size: Tamaño de batch
        logger: Instancia de logger
        
    Returns:
        Objeto TranscriptionResult
    """
    # Registrar parámetros de transcripción
    logger.info(LOG_TASK, task_value)
    logger.info(LOG_LANGUAGE, "Auto-detect" if language is None else language)
    logger.info(LOG_SEGMENT_BATCH, chunk_length, batch_size)
    
    # Extraer segmentos de hablante y agrupar por hablante
    speaker_segments = extract_speaker_segments(diar_segments)
    grouped_turns = group_turns_by_speaker(speaker_segments)
    
    # Procesar cada turno
    all_chunks = []
    total_processing_time = 0.0
    
    for turn in grouped_turns:
        # Extraer información del turno
        turn_start = turn["start"]
        turn_end = turn["end"]
        speaker = turn["speaker"]
        
        # Procesar segmento de audio
        turn_audio = slice_audio(audio, turn_start, turn_end)
        optimal_chunk_length = optimize_chunk_length(turn_end - turn_start, chunk_length)
        
        # Transcribir segmento
        turn_result = perform_transcription(
            pipeline=pipeline,
            audio_data=turn_audio,
            task=task_value,
            language=language,
            chunk_length=optimal_chunk_length,
            batch_size=batch_size,
        )
        total_processing_time += turn_result.processing_time
        
        # Procesar chunks de este turno
        processed_chunks = process_turn_chunks(
            turn_result.chunks, turn_start, turn_end, speaker, logger
        )
        
        # Añadir chunks a la colección
        all_chunks.extend(processed_chunks)
    
    # Ordenar chunks por tiempo de inicio
    all_chunks.sort(key=lambda c: c["timestamp"][0] if c["timestamp"][0] is not None else 0)
    
    # Calcular métricas
    audio_duration = audio["waveform"].shape[1] / audio["sample_rate"]
    speed_factor = audio_duration / total_processing_time if total_processing_time > 0 else float("inf")
    
    # Crear resultado
    return TranscriptionResult(
        text=" ".join(c["text"] for c in all_chunks),
        chunks=all_chunks,
        audio_duration=audio_duration,
        processing_time=total_processing_time,
        speed_factor=speed_factor,
    )


def extract_speaker_segments(
    diar_segments: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Extrae segmentos de hablante desde la diarización."""
    return [
        {"start": seg["start"], "end": seg["end"], "speaker": seg["speaker"]}
        for seg in diar_segments
    ]


def optimize_chunk_length(
    turn_duration: float, 
    max_chunk_length: int
) -> int:
    """Optimiza longitud de chunk basado en duración del turno."""
    return min(max_chunk_length, max(1, int(turn_duration + 0.5)))


def process_turn_chunks(
    chunks: List[Dict[str, Any]],
    turn_start: float,
    turn_end: float, 
    speaker: str,
    logger: logging.Logger
) -> List[Dict[str, Any]]:
    """Procesa chunks de un turno ajustando timestamps y asignando hablante."""
    processed = []
    for chunk in chunks:
        start_time, end_time = chunk["timestamp"]
        logger.debug(f"Timestamp del chunk: {chunk['timestamp']} (inicio={start_time}, fin={end_time})")
        
        # Ajustar timestamps
        chunk["timestamp"] = adjust_timestamps(start_time, end_time, turn_start, turn_end)
        
        # Asignar hablante
        chunk["speaker"] = speaker
        processed.append(chunk)
        
    return processed


def adjust_timestamps(
    start_time: Optional[float],
    end_time: Optional[float], 
    turn_start: float,
    turn_end: float
) -> Tuple[Optional[float], Optional[float]]:
    """
    Ajusta timestamps locales a línea de tiempo global, manejando valores None con seguridad.
    
    Args:
        start_time: Tiempo de inicio local (puede ser None)
        end_time: Tiempo de fin local (puede ser None)
        turn_start: Tiempo de inicio global del turno contenedor
        turn_end: Tiempo de fin global del turno contenedor
        
    Returns:
        Tupla de (start_time, end_time) ajustados con valores None manejados
    """
    if end_time is None:
        # Si el tiempo de fin es None, usar el fin del turno
        return (
            start_time + turn_start if start_time is not None else turn_start,
            turn_end
        )
    elif start_time is None:
        # Si el tiempo de inicio es None, usar el inicio del turno
        return (turn_start, end_time + turn_start)
    else:
        # Caso normal: ajustar ambos timestamps
        return (start_time + turn_start, end_time + turn_start)


def export_results(
    file_path: Path,
    transcription_result: TranscriptionResult,
    aligned_chunks: List[Dict[str, Any]],
    formats: List[str],
    logger: logging.Logger,
    grouping_mode: Union[GroupingMode, str] = GroupingMode.sentences,
    max_chars: int = 80,
    max_duration_s: float = 10.0
) -> None:
    """
    Exporta resultados en los formatos solicitados.
    
    Args:
        file_path: Ruta del archivo original
        transcription_result: Resultado de transcripción
        aligned_chunks: Chunks alineados con información de hablante
        formats: Lista de formatos de salida
        logger: Instancia de logger
        grouping_mode: Modo de agrupación (GroupingMode enum)
        max_chars: Máximo de caracteres por segmento
        max_duration_s: Máxima duración en segundos por segmento
    """
    base_path = get_output_base_path(file_path, "process")
    logger.info(MSG_SAVING_RESULTS, file_path.name)
    
    for fmt in formats:
        fmt = fmt.lower()
        if fmt == "json":
            save_json(base_path, format_transcription_result(transcription_result))
            logger.info(MSG_FILE_SAVED, "JSON", base_path.with_suffix(".json").name)
        elif fmt in ("txt", "srt", "vtt"):
            save_subtitles(
                transcription_result,
                base_path.with_suffix(f".{fmt}"),
                fmt,
                with_speaker=True,
                chunks=aligned_chunks,
                grouping_mode=grouping_mode,
                max_chars=max_chars,
                max_duration_s=max_duration_s
            )
            logger.info(MSG_FILE_SAVED, fmt.upper(), base_path.with_suffix(f".{fmt}").name)
        else:
            logger.warning(MSG_UNKNOWN_FORMAT, fmt)


def diarize_file(
    audio_path: Path,
    pipeline: Any,
    num_speakers: Optional[int] = None,
    device: Optional[str] = None,
    use_cache: bool = True
) -> tuple[DiarizationResult, Dict[str, Any]]:
    """
    Diariza un archivo de audio o video.

    *Devuelve tanto* el resultado de diarización como el audio cargado,
    para que el llamador pueda reutilizar el audio y evitar carga redundante.
    
    Args:
        audio_path: Ruta al archivo de audio o video
        pipeline: Pipeline de diarización
        num_speakers: Número de hablantes (opcional)
        device: Dispositivo para procesamiento (opcional)
        use_cache: Si se debe usar el sistema de caché para audio
    
    Returns:
        Tupla de (resultado de diarización, audio cargado)
    """
    # Usar caché de audio si está habilitado
    audio = load_media(audio_path, device, use_cache=use_cache)
    result = perform_diarization(pipeline, audio, num_speakers)

    return result, audio


def transcribe_file(
    audio_path: Path,
    pipeline: Any,
    task: str = DEFAULT_TASK.value,
    language: Optional[str] = DEFAULT_LANGUAGE,
    chunk_length: int = DEFAULT_CHUNK_LENGTH,
    batch_size: int = DEFAULT_BATCH_SIZE,
    device: Optional[str] = None,
    logger: Optional[logging.Logger] = None,
    use_cache: bool = True
) -> TranscriptionResult:
    """
    Transcribe un archivo de audio o video.

    Carga el medio con `load_media` y ejecuta la transcripción usando
    `perform_transcription`.
    
    Args:
        audio_path: Ruta al archivo de audio o video
        pipeline: Pipeline de transcripción
        task: Tarea a realizar (transcribe/translate)
        language: Código de idioma (opcional)
        chunk_length: Longitud de chunk en segundos
        batch_size: Tamaño de batch
        device: Dispositivo para procesamiento (opcional)
        logger: Logger personalizado (opcional)
        use_cache: Si se debe usar el sistema de caché para audio
        
    Returns:
        Resultado de transcripción
    """
    logger = logger or logging.getLogger("wx3.transcribe")
    logger.info(LOG_TRANSCRIBING, audio_path.name)

    # Registrar resumen de opciones
    logger.info(LOG_TASK, task)
    logger.info(LOG_LANGUAGE, "Auto-detect" if language is None else language)
    logger.info(LOG_SEGMENT_BATCH, chunk_length, batch_size)

    # Usar caché de audio si está habilitado
    audio = load_media(audio_path, device, use_cache=use_cache)

    return perform_transcription(
        pipeline,
        audio,
        task=task,
        language=language,
        chunk_length=chunk_length,
        batch_size=batch_size,
    )


def get_output_base_path(audio_path: Path, command_name: str, *extra_parts: str) -> Path:
    """Genera una ruta base para archivos de salida siguiendo el patrón estándar.
    
    Args:
        audio_path: Ruta al archivo original
        command_name: Nombre del comando (transcribe, diarize, process)
        *extra_parts: Partes adicionales para el nombre (opcional)
    """
    if not extra_parts:
        return audio_path.with_name(f"{audio_path.stem}-{command_name}")
    
    extra_suffix = "-".join(extra_parts)
    return audio_path.with_name(f"{audio_path.stem}-{command_name}-{extra_suffix}")


def process_file(
    file_path: Path,
    diar_pipeline: Any,
    trans_pipeline: Any,
    task: str,
    language: Optional[str],
    chunk_length: int,
    batch_size: int,
    formats: List[str],
    num_speakers: Optional[int] = None,
    device_str: Optional[str] = None,
    speaker_names: Optional[List[str]] = None,
    logger: Optional[logging.Logger] = None,
    save_intermediate: bool = False,
    use_cache: bool = True,
    grouping_mode: Union[GroupingMode, str] = GroupingMode.sentences,
    max_chars: int = 80,
    max_duration_s: float = 10.0
) -> Dict[str, Any]:
    """
    Procesa un archivo con diarización y transcripción.
    
    Args:
        file_path: Ruta al archivo a procesar
        diar_pipeline: Pipeline de diarización
        trans_pipeline: Pipeline de transcripción
        task: Tarea a realizar ('transcribe' o 'translate')
        language: Código de idioma (o None para detección automática)
        chunk_length: Longitud de chunk en segundos
        batch_size: Tamaño de batch
        formats: Formatos de salida a guardar
        num_speakers: Número de hablantes (opcional)
        device_str: Dispositivo a usar (opcional)
        speaker_names: Nombres de hablantes personalizados (opcional)
        logger: Logger personalizado (opcional)
        save_intermediate: Si se deben guardar resultados intermedios
        use_cache: Si se debe usar el sistema de caché para audio
        grouping_mode: Modo de agrupación (GroupingMode enum)
        max_chars: Máximo de caracteres por segmento
        max_duration_s: Máxima duración en segundos por segmento
        
    Returns:
        Diccionario con resultados del procesamiento
    """
    logger = logger or logging.getLogger("wx3.processor")
    
    # 1. Diarización
    diar_segments, audio = prepare_diarization(
        file_path, diar_pipeline, num_speakers, device_str, logger, 
        save_intermediate=save_intermediate, use_cache=use_cache
    )
    
    # 2. Transcripción
    trans_result = transcribe_by_speaker_turns(
        diar_segments, audio, trans_pipeline, task, language, 
        chunk_length, batch_size, logger
    )
    
    # Guardar transcripción intermedia si se solicita
    if save_intermediate:
        base_t = get_output_base_path(file_path, "process", "transcribe", "intermediate")
        save_json(base_t, format_transcription_result(trans_result))
        logger.info(f"Transcripción intermedia guardada: {base_t.with_suffix('.json').name}")
    
    # 3-4. Alineación y asignación de nombres
    aligned_chunks = align_diarization_with_transcription(
        diar_segments, trans_result.chunks
    )
    
    if speaker_names:
        apply_speaker_names(aligned_chunks, speaker_names)
    
    # 5. Exportación
    export_results(
        file_path, 
        trans_result, 
        aligned_chunks, 
        formats, 
        logger,
        grouping_mode=grouping_mode,
        max_chars=max_chars,
        max_duration_s=max_duration_s
    )
    
    # Devolver resultados para posible uso posterior
    return {
        "diarization": diar_segments,
        "transcription": format_transcription_result(trans_result),
        "aligned_chunks": aligned_chunks
    }