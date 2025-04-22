from __future__ import annotations

import logging
import functools
from pathlib import Path
from typing import Any, List, Optional, Dict, Callable, TypeVar, Tuple, Union

import typer
from rich.panel import Panel
from rich.console import Console

from constants import (
    Task, Device, LogLevel, DEFAULT_MODEL, DEFAULT_TASK, DEFAULT_LANGUAGE,
    DEFAULT_CHUNK_LENGTH, DEFAULT_BATCH_SIZE, DEFAULT_ATTN_TYPE,
    DEFAULT_LOG_LEVEL, DEFAULT_FORMATS, MSG_NO_FILES_FOUND,
    # Added new constants
    MSG_PROCESSING_FILES, MSG_PROCESSING_FILE, MSG_SAVING_RESULTS,
    MSG_FILE_SAVED, MSG_UNKNOWN_FORMAT, MSG_ERROR_PROCESSING,
    HELP_APP, HELP_AUDIO_INPUTS, HELP_MODEL, HELP_TASK, HELP_LANG,
    HELP_CHUNK_LENGTH, HELP_BATCH_SIZE, HELP_ATTN_TYPE, HELP_DEVICE,
    HELP_FORMATS, HELP_LOG_LEVEL, HELP_LOG_FILE, HELP_SHOW_FORMATS,
    HELP_HF_TOKEN, HELP_NUM_SPEAKERS, HELP_TRANSCRIBE, HELP_DIARIZE,
    HELP_PROCESS, PANEL_TITLE, PANEL_SUPPORTED_FORMATS, PANEL_AUDIO_FORMATS,
    PANEL_VIDEO_FORMATS, LOG_LOAD_TIMES_TITLE, LOG_LOAD_TIME_ENTRY,
    LOG_INIT_TRANSCRIPTION, LOG_INIT_DIARIZATION, LOG_INIT_PIPELINES,
    LOG_TRANSCRIBING, LOG_DIARIZING, LOG_TASK, LOG_LANGUAGE,
    LOG_SEGMENT_BATCH, LOG_NUM_SPEAKERS
)

from transcription import (
    TranscriptionResult,
    create_pipeline as create_transcription_pipeline,
    format_transcription_result,
    perform_transcription,
)
from diarization import (
    DiarizationResult,
    create_pipeline as create_diarization_pipeline,
    format_diarization_result,
    perform_diarization,
)
from lazy_loading import get_loading_times
from output_formatters import save_json, save_subtitles
from alignment import align_diarization_with_transcription, group_turns_by_speaker, slice_audio, apply_speaker_names
from input_media import load_media, get_supported_extensions

# Types for annotations
T = TypeVar('T')
CommandResult = TypeVar('CommandResult')

# Rich console for formatting
console = Console()

app = typer.Typer(
    help=HELP_APP,
    add_completion=False,
    no_args_is_help=True,
)

# Centralized utility functions
def resolve_device(device: Device | str) -> Optional[str]:
    """Resolves the device selection."""
    device_str = str(device)
    # Extract only the value part if it's an enum representation
    if "." in device_str:
        device_str = device_str.split(".")[-1]
        
    return None if device_str == "auto" else device_str

def expand_audio_inputs(inputs: List[str]) -> List[Path]:
    """Expands patterns and verifies input files."""
    files = []
    for entry in inputs:
        path = Path(entry)
        if any(char in entry for char in "*?["):
            files.extend(path.parent.glob(path.name))
        elif path.is_file():
            files.append(path)
    return list({f.resolve() for f in files if f.exists()})

def get_output_base_path(audio_path: Path, command_name: str, *extra_parts: str) -> Path:
    """Generates a base path for output files following the standard pattern.
    
    Args:
        audio_path: Path to the original file
        command_name: Command name (transcribe, diarize, process)
        *extra_parts: Additional parts for the name (optional)
    """
    if not extra_parts:
        return audio_path.with_name(f"{audio_path.stem}-{command_name}")
    
    extra_suffix = "-".join(extra_parts)
    return audio_path.with_name(f"{audio_path.stem}-{command_name}-{extra_suffix}")

def show_supported_formats() -> None:
    """Shows information about supported formats in the command help."""
    formats_info = get_supported_extensions()
    console.print(Panel(
        "\n".join([
            f"[bold cyan]{PANEL_SUPPORTED_FORMATS}[/]",
            f"[yellow]{PANEL_AUDIO_FORMATS.format(', '.join(formats_info['audio']))}[/]",
            f"[yellow]{PANEL_VIDEO_FORMATS.format(', '.join(formats_info['video']))}[/]"
        ]),
        title=PANEL_TITLE,
        expand=False
    ))

def show_loading_times(logger: logging.Logger) -> None:
    """Shows loading times if requested."""
    loading_times = get_loading_times()
    if loading_times:
        logger.info(LOG_LOAD_TIMES_TITLE)
        for m, t in loading_times.items():
            logger.info(LOG_LOAD_TIME_ENTRY, m, t)

def setup_logging(log_level: LogLevel, log_file: Optional[str]) -> None:
    """Configures the logging system based on parameters."""
    from logging_config import LogConfig, LogLevel as LG, configure_logging
    configure_logging(LogConfig(level=LG[log_level.name], log_file=log_file))

def validate_inputs(inputs: List[Path]) -> None:
    """Validates that there are valid input files."""
    if not inputs:
        logger = logging.getLogger("wx3")
        logger.error(MSG_NO_FILES_FOUND)
        
        # Show supported formats when there are no valid files
        show_supported_formats()
        
        typer.secho(MSG_NO_FILES_FOUND, fg=typer.colors.RED)
        raise typer.Exit(1)

# Specific functions for each type of processing
def transcribe_file(
    audio_path: Path,
    command_name: str,
    pipeline: Any,
    task: str = DEFAULT_TASK.value,
    language: Optional[str] = DEFAULT_LANGUAGE,
    chunk_length: int = DEFAULT_CHUNK_LENGTH,
    batch_size: int = DEFAULT_BATCH_SIZE,
    device: Optional[str] = None,
) -> TranscriptionResult:
    """
    Transcribe un archivo de audio o video.

    Carga el medio con `load_media` y ejecuta la transcripción mediante
    `perform_transcription`. Devuelve únicamente el resultado de la
    transcripción; el audio ya cargado no se retorna porque, en el
    comando simple `transcribe`, no se reutiliza.
    """
    logger = logging.getLogger(f"wx3.{command_name}")
    logger.info(LOG_TRANSCRIBING, audio_path.name)

    # Resumen de opciones
    logger.info(LOG_TASK, task)
    logger.info(LOG_LANGUAGE, "Auto-detect" if language is None else language)
    logger.info(LOG_SEGMENT_BATCH, chunk_length, batch_size)

    audio = load_media(audio_path, device)

    return perform_transcription(
        pipeline,
        audio,
        task=task,
        language=language,
        chunk_length=chunk_length,
        batch_size=batch_size,
    )


def diarize_file(
    audio_path: Path,
    command_name: str,
    pipeline: Any,
    num_speakers: Optional[int] = None,
    device: Optional[str] = None,
) -> tuple[DiarizationResult, AudioData]:
    """
    Diariza un archivo de audio o video.

    *Devuelve tanto* el resultado de diarización como el audio cargado,
    de modo que quien llame (p. ej. `process`) pueda reutilizar el audio
    y evitar una lectura redundante.
    """
    logger = logging.getLogger(f"wx3.{command_name}")
    logger.info(LOG_DIARIZING, audio_path.name)

    logger.info(
        LOG_NUM_SPEAKERS, "Auto-detect" if num_speakers is None else num_speakers
    )

    audio = load_media(audio_path, device)
    result = perform_diarization(pipeline, audio, num_speakers)

    return result, audio


# CLI command implementations
@app.command()
def transcribe(
    audio_inputs: List[str] = typer.Argument(..., help=HELP_AUDIO_INPUTS),
    model: str = typer.Option(DEFAULT_MODEL, help=HELP_MODEL),
    task: Task = typer.Option(DEFAULT_TASK, help=HELP_TASK),
    lang: Optional[str] = typer.Option(DEFAULT_LANGUAGE, help=HELP_LANG),
    chunk_length: int = typer.Option(DEFAULT_CHUNK_LENGTH, help=HELP_CHUNK_LENGTH),
    batch_size: int = typer.Option(DEFAULT_BATCH_SIZE, help=HELP_BATCH_SIZE),
    attn_type: str = typer.Option(DEFAULT_ATTN_TYPE, help=HELP_ATTN_TYPE),
    device: Device = typer.Option(Device.auto, help=HELP_DEVICE),
    formats: List[str] = typer.Option(DEFAULT_FORMATS["transcribe"], "--format", "-f", help=HELP_FORMATS, case_sensitive=False),
    log_level: LogLevel = typer.Option(DEFAULT_LOG_LEVEL, "--log-level", "-l", help=HELP_LOG_LEVEL),
    log_file: Optional[str] = typer.Option(None, help=HELP_LOG_FILE),
    show_formats: bool = typer.Option(False, "--show-formats", help=HELP_SHOW_FORMATS),
):
    """Transcribe audio/video files."""
    # Configure logging
    setup_logging(log_level, log_file)
    logger = logging.getLogger("wx3.transcribe")
    
    # Show supported formats if requested
    if show_formats:
        show_supported_formats()
        return
    
    # Expand and validate inputs
    files = expand_audio_inputs(audio_inputs)
    validate_inputs(files)
    
    # Create pipeline
    device_str = resolve_device(device)
    logger.info(LOG_INIT_TRANSCRIPTION, model, device_str or 'auto')
    pipeline = create_transcription_pipeline(model, device_str, attn_type)
    
    total_files = len(files)
    logger.info(MSG_PROCESSING_FILES, total_files)
    
    for idx, audio_path in enumerate(files, start=1):
        try:
            logger.info(MSG_PROCESSING_FILE, idx, total_files, audio_path.name)
            
            # Ya no devolvemos audio, solo el resultado:
            result = transcribe_file(
                audio_path=audio_path,
                command_name="transcribe",
                pipeline=pipeline,
                task=task.value,
                language=lang,
                chunk_length=chunk_length,
                batch_size=batch_size,
                device=device_str,
            )

            # — Guardar resultados —
            base = get_output_base_path(audio_path, "transcribe")
            logger.info(MSG_SAVING_RESULTS, audio_path.name)
            for fmt in formats:
                f = fmt.lower()
                if f == "json":
                    save_json(base, format_transcription_result(result))
                    logger.info(MSG_FILE_SAVED, "JSON", base.with_suffix(".json").name)
                elif f in ("txt", "srt", "vtt"):
                    save_subtitles(result, base.with_suffix(f".{f}"), f)
                    logger.info(MSG_FILE_SAVED, f.upper(), base.with_suffix(f".{f}").name)
                else:
                    logger.warning(MSG_UNKNOWN_FORMAT, fmt)

        except Exception as e:
            logger.error(MSG_ERROR_PROCESSING, audio_path.name, str(e))
            logger.exception(e)
   
    # Show loading times if requested
    show_loading_times(logger)

@app.command()
def diarize(
    audio_inputs: List[str] = typer.Argument(..., help=HELP_AUDIO_INPUTS),
    hf_token: str = typer.Option(..., help=HELP_HF_TOKEN),
    num_speakers: Optional[int] = typer.Option(None, help=HELP_NUM_SPEAKERS),
    device: Device = typer.Option(Device.auto, help=HELP_DEVICE),
    formats: List[str] = typer.Option(DEFAULT_FORMATS["diarize"], "--format", "-f", help=HELP_FORMATS, case_sensitive=False),
    log_level: LogLevel = typer.Option(DEFAULT_LOG_LEVEL, "--log-level", "-l", help=HELP_LOG_LEVEL),
    log_file: Optional[str] = typer.Option(None, help=HELP_LOG_FILE),
    show_formats: bool = typer.Option(False, "--show-formats", help=HELP_SHOW_FORMATS),
):
    """Diarize audio/video files."""
    # Configure logging
    setup_logging(log_level, log_file)
    logger = logging.getLogger("wx3.diarize")
    
    # Show supported formats if requested
    if show_formats:
        show_supported_formats()
        return
    
    # Expand and validate inputs
    files = expand_audio_inputs(audio_inputs)
    validate_inputs(files)
    
    # Create pipeline
    device_str = resolve_device(device)
    logger.info(LOG_INIT_DIARIZATION, device_str or 'auto')
    pipeline = create_diarization_pipeline(hf_token, device_str)
    
    total_files = len(files)
    logger.info(MSG_PROCESSING_FILES, total_files)
    
    for idx, audio_path in enumerate(files, 1):
        try:
            logger.info(MSG_PROCESSING_FILE, idx, total_files, audio_path.name)
            
            result, audio = diarize_file(
                audio_path=audio_path,
                command_name="diarize",
                pipeline=pipeline,
                num_speakers=num_speakers,
                device=device_str
            )
            
            # Save results
            base = get_output_base_path(audio_path, "diarize")
            logger.info(MSG_SAVING_RESULTS, audio_path.name)
            
            for fmt in formats:
                f = fmt.lower()
                if f == "json":
                    save_json(base, format_diarization_result(result))
                    logger.info(MSG_FILE_SAVED, "JSON", base.with_suffix('.json').name)
                else:
                    logger.warning(MSG_UNKNOWN_FORMAT, fmt)
                    
        except Exception as e:
            logger.error(MSG_ERROR_PROCESSING, audio_path.name, str(e))
            logger.exception(e)
    
    # Show loading times if requested
    show_loading_times(logger)



@app.command()
def process(
    audio_inputs: List[str] = typer.Argument(..., help=HELP_AUDIO_INPUTS),
    model: str = typer.Option(DEFAULT_MODEL, help=HELP_MODEL),
    task: Task = typer.Option(DEFAULT_TASK, help=HELP_TASK),
    lang: Optional[str] = typer.Option(DEFAULT_LANGUAGE, help=HELP_LANG),
    chunk_length: int = typer.Option(DEFAULT_CHUNK_LENGTH, help=HELP_CHUNK_LENGTH),
    batch_size: int = typer.Option(DEFAULT_BATCH_SIZE, help=HELP_BATCH_SIZE),
    attn_type: str = typer.Option(DEFAULT_ATTN_TYPE, help=HELP_ATTN_TYPE),
    num_speakers: Optional[int] = typer.Option(None, help=HELP_NUM_SPEAKERS),
    hf_token: str = typer.Option(..., help=HELP_HF_TOKEN),
    device: Device = typer.Option(Device.auto, help=HELP_DEVICE),
    formats: List[str] = typer.Option(
        DEFAULT_FORMATS["process"], "--format", "-f",
        help=HELP_FORMATS, case_sensitive=False
    ),
    log_level: LogLevel = typer.Option(
        DEFAULT_LOG_LEVEL, "--log-level", "-l", help=HELP_LOG_LEVEL
    ),
    log_file: Optional[str] = typer.Option(None, help=HELP_LOG_FILE),
    show_formats: bool = typer.Option(False, "--show-formats", help=HELP_SHOW_FORMATS),
    speaker_names: Optional[str] = typer.Option(
        None, help="Lista separada por coma con nombres de hablantes para reemplazar SPEAKER_xx"
    )
):
    """
    Pipeline combinado: diarización ➜ transcripción ➜ alineado/exportación.
    Reutiliza el audio cargado en la etapa de diarización para evitar
    una segunda lectura.
    """
    # ───── Configuración inicial ─────
    setup_logging(log_level, log_file)
    logger = logging.getLogger("wx3.process")

    if show_formats:
        show_supported_formats()
        return

    files = expand_audio_inputs(audio_inputs)
    validate_inputs(files)

    device_str = resolve_device(device)
    logger.info(LOG_INIT_PIPELINES, model, device_str or "auto")
    pipe_d = create_diarization_pipeline(hf_token, device_str)
    pipe_t = create_transcription_pipeline(model, device_str, attn_type)

    logger.info(MSG_PROCESSING_FILES, len(files))

    for idx_file, audio_path in enumerate(files, start=1):
        logger.info(MSG_PROCESSING_FILE, idx_file, len(files), audio_path.name)
        try:
            # ───── 1 · DIARIZACIÓN ─────
            dres, audio_full = diarize_file(
                audio_path, "diarize", pipe_d, num_speakers, device_str
            )
            diar_segments = format_diarization_result(dres)["speakers"]
            base_d = get_output_base_path(
                audio_path, "process", "diarize", "intermediate"
            )
            save_json(base_d, format_diarization_result(dres))

            # ───── 2 · TRANSCRIPCIÓN POR TURNOS ─────
            turns_dicts = [
                {"start": s["start"], "end": s["end"], "speaker": s["speaker"]}
                for s in diar_segments
            ]
            grouped = group_turns_by_speaker(turns_dicts)

            all_chunks: List[Dict[str, Any]] = []
            total_proc_time = 0.0

            for seg in grouped:
                t_start, t_end, spk = seg["start"], seg["end"], seg["speaker"]
                seg_audio = slice_audio(audio_full, t_start, t_end)

                seg_res = perform_transcription(
                    pipeline=pipe_t,
                    audio_data=seg_audio,
                    task=task.value,
                    language=lang,
                    chunk_length=min(chunk_length, int(t_end - t_start + 1)),
                    batch_size=batch_size,
                )
                total_proc_time += seg_res.processing_time

                for ch in seg_res.chunks:
                    st, et = ch["timestamp"]
                    ch["timestamp"] = (st + t_start, et + t_start)
                    ch["speaker"] = spk
                all_chunks.extend(seg_res.chunks)

            all_chunks.sort(key=lambda c: c["timestamp"][0])

            audio_dur = (
                audio_full["waveform"].shape[1] / audio_full["sample_rate"]
            )
            speed = audio_dur / total_proc_time if total_proc_time > 0 else float("inf")

            tres = TranscriptionResult(
                text=" ".join(c["text"] for c in all_chunks),
                chunks=all_chunks,
                audio_duration=audio_dur,
                processing_time=total_proc_time,
                speed_factor=speed,
            )
            base_t = get_output_base_path(
                audio_path, "process", "transcribe", "intermediate"
            )
            save_json(base_t, format_transcription_result(tres))

            # ───── 3 · (OPCIONAL) ALINEADO ─────
            aligned_chunks = align_diarization_with_transcription(
                diar_segments, tres.chunks
            )

            if speaker_names:
                names_list = [name.strip() for name in speaker_names.split(",")]
                apply_speaker_names(aligned_chunks, names_list)

            # ───── 4 · EXPORTACIÓN FINAL ─────
            base_p = get_output_base_path(audio_path, "process")
            for fmt in formats:
                f = fmt.lower()
                if f == "json":
                    save_json(base_p, format_transcription_result(tres))
                    logger.info(MSG_FILE_SAVED, "JSON", base_p.with_suffix(".json").name)
                elif f in ("txt", "srt", "vtt"):
                    save_subtitles(
                        tres,
                        base_p.with_suffix(f".{f}"),
                        f,
                        with_speaker=True,
                        chunks=aligned_chunks,
                    )
                    logger.info(
                        MSG_FILE_SAVED, f.upper(), base_p.with_suffix(f".{f}").name
                    )
                else:
                    logger.warning(MSG_UNKNOWN_FORMAT, fmt)

        except Exception as exc:  # noqa: WPS424 – registro de excepción amplia
            logger.error(MSG_ERROR_PROCESSING, audio_path.name, exc)
            logger.exception(exc)
            continue

    show_loading_times(logger)



if __name__ == "__main__":
    app()