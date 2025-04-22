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
import torch
from constants import Device

def resolve_device(device: Device) -> str:
    """
    Resolves a Device enum value to a torch.device instance.

    Args:
        device: Enum value indicating the desired device.

    Returns:
        String representation of the device compatible with PyTorch.
    
    Raises:
        ValueError: If the enum value is not recognized or not supported.
    """
    match device:
        case Device.auto:
            return "cuda" if torch.cuda.is_available() else "cpu"

        case Device.cpu:
            return "cpu"

        case Device.mps:
            if torch.backends.mps.is_available():
                return "mps"
            raise RuntimeError("MPS is not available. Requires macOS with Apple Silicon and PyTorch ≥ 1.13.")

        case Device.cuda:
            if not torch.cuda.is_available():
                raise RuntimeError("CUDA is not available on this system.")
            return "cuda"

        case _:
            raise ValueError(f"Unsupported device: {device}")


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


# --- Shared Command Utility Functions ---

def setup_command(
    log_level: LogLevel, 
    log_file: Optional[str], 
    show_formats: bool,
    audio_inputs: List[str]
) -> Optional[List[Path]]:
    """
    Common setup for CLI commands.
    
    Args:
        log_level: Logging level
        log_file: Optional log file path
        show_formats: Whether to show supported formats
        audio_inputs: List of audio input paths
        
    Returns:
        List of expanded and validated files, or None if showing formats
    """
    setup_logging(log_level, log_file)
    
    if show_formats:
        show_supported_formats()
        return None
        
    files = expand_audio_inputs(audio_inputs)
    validate_inputs(files)
    
    return files


def prepare_diarization(
    file_path: Path,
    pipeline: Any,
    num_speakers: Optional[int],
    device_str: Optional[str],
    logger: logging.Logger,
    save_intermediate: bool = False
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Prepare diarization data for a file.
    
    Args:
        file_path: Path to audio file
        pipeline: Diarization pipeline
        num_speakers: Number of speakers (optional)
        device_str: Device string
        logger: Logger instance
        save_intermediate: Whether to save intermediate results
        
    Returns:
        Tuple of (diarization segments, loaded audio)
    """
    logger.info(LOG_DIARIZING, file_path.name)
    logger.info(LOG_NUM_SPEAKERS, "Auto-detect" if num_speakers is None else num_speakers)
    
    # Perform diarization without saving files
    diar_result, audio = diarize_file(
        audio_path=file_path,
        command_name="process",
        pipeline=pipeline,
        num_speakers=num_speakers,
        device=device_str
    )
    
    # Extract segments from result
    diar_segments = format_diarization_result(diar_result)["speakers"]
    
    # Optionally save intermediate result
    if save_intermediate:
        base_path = get_output_base_path(file_path, "process", "diarize", "intermediate")
        save_json(base_path, format_diarization_result(diar_result))
        logger.info(f"Intermediate diarization saved: {base_path.with_suffix('.json').name}")
    
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
    Transcribe audio by processing each speaker turn separately.
    
    Args:
        diar_segments: Diarization segments
        audio: Audio data
        pipeline: Transcription pipeline
        task_value: Task value (transcribe/translate)
        language: Language code
        chunk_length: Chunk length in seconds
        batch_size: Batch size
        logger: Logger instance
        
    Returns:
        TranscriptionResult object
    """
    # Log transcription parameters
    logger.info(LOG_TASK, task_value)
    logger.info(LOG_LANGUAGE, "Auto-detect" if language is None else language)
    logger.info(LOG_SEGMENT_BATCH, chunk_length, batch_size)
    
    # Extract speaker segments and group by speaker
    speaker_segments = [
        {"start": seg["start"], "end": seg["end"], "speaker": seg["speaker"]}
        for seg in diar_segments
    ]
    grouped_turns = group_turns_by_speaker(speaker_segments)
    
    # Process each turn
    all_chunks = []
    total_processing_time = 0.0
    
    for turn in grouped_turns:
        # Extract turn information
        turn_start = turn["start"]
        turn_end = turn["end"]
        speaker = turn["speaker"]
        
        # Process audio segment
        turn_audio = slice_audio(audio, turn_start, turn_end)
        optimal_chunk_length = min(chunk_length, int(turn_end - turn_start + 1))
        
        # Transcribe segment
        turn_result = perform_transcription(
            pipeline=pipeline,
            audio_data=turn_audio,
            task=task_value,
            language=language,
            chunk_length=optimal_chunk_length,
            batch_size=batch_size,
        )
        total_processing_time += turn_result.processing_time
        
        # Process chunks from this turn
        for chunk in turn_result.chunks:
            start_time, end_time = chunk["timestamp"]
            logger.debug(f"Chunk timestamp: {chunk['timestamp']} (start={start_time}, end={end_time})")
            
            # Adjust timestamps
            chunk["timestamp"] = adjust_timestamps(start_time, end_time, turn_start, turn_end)
                
            # Assign speaker
            chunk["speaker"] = speaker
            
        # Add chunks to collection
        all_chunks.extend(turn_result.chunks)
    
    # Sort chunks by start time
    all_chunks.sort(key=lambda c: c["timestamp"][0])
    
    # Calculate metrics
    audio_duration = audio["waveform"].shape[1] / audio["sample_rate"]
    speed_factor = audio_duration / total_processing_time if total_processing_time > 0 else float("inf")
    
    # Create result
    return TranscriptionResult(
        text=" ".join(c["text"] for c in all_chunks),
        chunks=all_chunks,
        audio_duration=audio_duration,
        processing_time=total_processing_time,
        speed_factor=speed_factor,
    )


def adjust_timestamps(
    start_time: Optional[float],
    end_time: Optional[float], 
    turn_start: float,
    turn_end: float
) -> Tuple[float, float]:
    """
    Adjust local timestamps to global timeline, handling None values safely.
    
    Args:
        start_time: Local start time (can be None)
        end_time: Local end time (can be None)
        turn_start: Global start time of the containing turn
        turn_end: Global end time of the containing turn
        
    Returns:
        Tuple of adjusted (start_time, end_time) with None values handled
    """
    if end_time is None:
        # If end time is None, use the end of the turn
        return (
            start_time + turn_start if start_time is not None else turn_start,
            turn_end
        )
    elif start_time is None:
        # If start time is None, use the start of the turn
        return (turn_start, end_time + turn_start)
    else:
        # Normal case: adjust both timestamps
        return (start_time + turn_start, end_time + turn_start)


def export_results(
    file_path: Path,
    transcription_result: TranscriptionResult,
    aligned_chunks: List[Dict[str, Any]],
    formats: List[str],
    logger: logging.Logger
) -> None:
    """
    Export results in the requested formats.
    
    Args:
        file_path: Original file path
        transcription_result: Transcription result
        aligned_chunks: Aligned chunks with speaker information
        formats: List of output formats
        logger: Logger instance
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
            )
            logger.info(MSG_FILE_SAVED, fmt.upper(), base_path.with_suffix(f".{fmt}").name)
        else:
            logger.warning(MSG_UNKNOWN_FORMAT, fmt)


def diarize_file(
    audio_path: Path,
    command_name: str,
    pipeline: Any,
    num_speakers: Optional[int] = None,
    device: Optional[str] = None,
) -> tuple[DiarizationResult, Dict[str, Any]]:
    """
    Diarizes an audio or video file.

    *Returns both* the diarization result and the loaded audio,
    so that the caller (e.g., `process`) can reuse the audio
    to avoid redundant loading.
    """
    audio = load_media(audio_path, device)
    result = perform_diarization(pipeline, audio, num_speakers)

    return result, audio


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
    Transcribes an audio or video file.

    Loads the media with `load_media` and runs transcription using
    `perform_transcription`. Only returns the transcription result;
    the loaded audio is not returned because it's not reused in the
    simple `transcribe` command.
    """
    logger = logging.getLogger(f"wx3.{command_name}")
    logger.info(LOG_TRANSCRIBING, audio_path.name)

    # Log options summary
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


# --- CLI Commands ---

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
    # Initial setup
    files = setup_command(log_level, log_file, show_formats, audio_inputs)
    if not files:
        return
    
    # Create pipeline
    logger = logging.getLogger("wx3.transcribe")
    device_str = resolve_device(device)
    logger.info(LOG_INIT_TRANSCRIPTION, model, device_str)
    pipeline = create_transcription_pipeline(model, device_str, attn_type)
    
    # Process files
    logger.info(MSG_PROCESSING_FILES, len(files))
    
    for file_idx, file_path in enumerate(files, start=1):
        try:
            logger.info(MSG_PROCESSING_FILE, file_idx, len(files), file_path.name)
            
            # Transcribe file
            result = transcribe_file(
                audio_path=file_path,
                command_name="transcribe",
                pipeline=pipeline,
                task=task.value,
                language=lang,
                chunk_length=chunk_length,
                batch_size=batch_size,
                device=device_str,
            )

            # Save results
            base_path = get_output_base_path(file_path, "transcribe")
            logger.info(MSG_SAVING_RESULTS, file_path.name)
            
            for fmt in formats:
                fmt = fmt.lower()
                if fmt == "json":
                    save_json(base_path, format_transcription_result(result))
                    logger.info(MSG_FILE_SAVED, "JSON", base_path.with_suffix(".json").name)
                elif fmt in ("txt", "srt", "vtt"):
                    save_subtitles(result, base_path.with_suffix(f".{fmt}"), fmt)
                    logger.info(MSG_FILE_SAVED, fmt.upper(), base_path.with_suffix(f".{fmt}").name)
                else:
                    logger.warning(MSG_UNKNOWN_FORMAT, fmt)

        except Exception as exc:
            logger.error(MSG_ERROR_PROCESSING, file_path.name, str(exc))
            logger.exception(exc)
   
    # Show loading times
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
    # Initial setup
    files = setup_command(log_level, log_file, show_formats, audio_inputs)
    if not files:
        return
    
    # Create pipeline
    logger = logging.getLogger("wx3.diarize")
    device_str = resolve_device(device)
    logger.info(LOG_INIT_DIARIZATION, device_str)
    pipeline = create_diarization_pipeline(hf_token, device_str)
    
    # Process files
    logger.info(MSG_PROCESSING_FILES, len(files))
    
    for file_idx, file_path in enumerate(files, start=1):
        try:
            logger.info(MSG_PROCESSING_FILE, file_idx, len(files), file_path.name)
            
            # Prepare diarization data (don't save intermediate results)
            diar_segments, _ = prepare_diarization(
                file_path, pipeline, num_speakers, device_str, logger, save_intermediate=False
            )
            
            # Create full diarization result
            diar_result = {"speakers": diar_segments}
            
            # Save results
            base_path = get_output_base_path(file_path, "diarize")
            logger.info(MSG_SAVING_RESULTS, file_path.name)
            
            for fmt in formats:
                fmt = fmt.lower()
                if fmt == "json":
                    save_json(base_path, diar_result)
                    logger.info(MSG_FILE_SAVED, "JSON", base_path.with_suffix('.json').name)
                else:
                    logger.warning(MSG_UNKNOWN_FORMAT, fmt)
                    
        except Exception as exc:
            logger.error(MSG_ERROR_PROCESSING, file_path.name, str(exc))
            logger.exception(exc)
    
    # Show loading times
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
        None, help="Comma-separated list of speaker names to replace SPEAKER_xx"
    )
):
    """
    Combined pipeline: diarization → transcription → alignment/export.
    Reuses audio loaded in the diarization stage to avoid a second read.
    """
    # Setup command
    files = setup_command(log_level, log_file, show_formats, audio_inputs)
    if not files:
        return
        
    # Setup pipelines
    logger = logging.getLogger("wx3.process")
    device_str = resolve_device(device)
    logger.info(LOG_INIT_PIPELINES, model, device_str or "auto")
    
    diar_pipeline = create_diarization_pipeline(hf_token, device_str)
    trans_pipeline = create_transcription_pipeline(model, device_str, attn_type)
    
    # Process files
    logger.info(MSG_PROCESSING_FILES, len(files))
    
    for file_idx, file_path in enumerate(files, start=1):
        logger.info(MSG_PROCESSING_FILE, file_idx, len(files), file_path.name)
        
        try:
            # 1. Diarization
            diar_segments, audio = prepare_diarization(
                file_path, diar_pipeline, num_speakers, device_str, logger, save_intermediate=True
            )
            
            # 2. Transcription by turns
            trans_result = transcribe_by_speaker_turns(
                diar_segments, audio, trans_pipeline, task.value, lang, 
                chunk_length, batch_size, logger
            )
            
            # Save intermediate transcription
            base_t = get_output_base_path(file_path, "process", "transcribe", "intermediate")
            save_json(base_t, format_transcription_result(trans_result))
            logger.info(f"Intermediate transcription saved: {base_t.with_suffix('.json').name}")
            
            # 3. Alignment
            aligned_chunks = align_diarization_with_transcription(diar_segments, trans_result.chunks)
            
            # 4. Apply speaker names if provided
            if speaker_names:
                names_list = [name.strip() for name in speaker_names.split(",")]
                apply_speaker_names(aligned_chunks, names_list)
                
            # 5. Export results
            export_results(file_path, trans_result, aligned_chunks, formats, logger)
            
        except Exception as exc:
            logger.error(MSG_ERROR_PROCESSING, file_path.name, exc)
            logger.exception(exc)
            
    # Show loading times
    show_loading_times(logger)


if __name__ == "__main__":
    app()