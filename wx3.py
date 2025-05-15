from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, List, Optional, Dict, Callable, TypeVar, Tuple, Union

import typer
from rich.panel import Panel
from rich.console import Console

from constants import *

from processor import (
    process_file,
    transcribe_file as processor_transcribe_file,
    diarize_file as processor_diarize_file,
    get_output_base_path
)
from pipelines import (
    get_transcription_pipeline,
    get_diarization_pipeline,
    get_pipeline_cache_info,
    clear_pipeline_cache
)
from transcription import (
    TranscriptionResult,
    format_transcription_result,
)
from diarization import (
    DiarizationResult,
    format_diarization_result,
)
from lazy_loading import get_loading_times
from output_formatters import save_json, save_subtitles
from input_media import (
    get_supported_extensions,
    get_cache_info as get_audio_cache_info,
    clear_audio_cache
)
T = TypeVar('T')
CommandResult = TypeVar('CommandResult')
console = Console()

app = typer.Typer(
    help=HELP_APP,
    add_completion=False,
    no_args_is_help=True,
)

from lazy_loading import lazy_load

def resolve_device(device: Device) -> str:
    """
    Resolves a Device enum value to a device string compatible with PyTorch.

    Args:
        device: Enum value indicating the desired device.

    Returns:
        String representation of the device compatible with PyTorch.

    Raises:
        ValueError: If the enum value is not recognized or not supported.
        RuntimeError: If a device (CUDA, MPS) is requested but not available.
    """
    torch = lazy_load("torch", "")

    match device:
        case Device.auto:
            return "cuda" if torch.cuda.is_available() else "cpu"

        case Device.cpu:
            return "cpu"

        case Device.mps:
            if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                return "mps"
            raise RuntimeError("MPS is not available. Requires macOS with Apple Silicon and PyTorch >= 1.13.")

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
        if any(char in entry for char in "*?["): # Check for glob patterns
            if path.parent.is_dir():
                files.extend(path.parent.glob(path.name))
            else:
                files.extend(Path(".").glob(entry))
        elif path.is_file():
            files.append(path)
    return list({f.resolve() for f in files if f.exists() and f.is_file()})


def show_supported_formats() -> None:
    """Shows information about supported formats in the command help."""
    rich_console = lazy_load("rich.console", "Console") # type: ignore
    rich_panel = lazy_load("rich.panel", "Panel") # type: ignore
    console_instance = rich_console()
    formats_info = get_supported_extensions()

    console_instance.print(rich_panel.Panel(
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
    from logging_config import LogConfig, LogLevel as LG_Enum, configure_logging
    configure_logging(LogConfig(level=LG_Enum[log_level.name], log_file=log_file))


def validate_inputs(inputs: List[Path]) -> None:
    """Validates that there are valid input files."""
    if not inputs:
        logger = logging.getLogger("wx3")
        logger.error(MSG_NO_FILES_FOUND)
        show_supported_formats()
        typer.secho(MSG_NO_FILES_FOUND, fg=typer.colors.RED)
        raise typer.Exit(1)

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


def transcribe_file_wrapper(
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

    Wrapper around processor_transcribe_file for compatibility.
    """
    logger = logging.getLogger(f"wx3.{command_name}")

    return processor_transcribe_file(
        audio_path,
        pipeline,
        task=task,
        language=language,
        chunk_length=chunk_length,
        batch_size=batch_size,
        device=device,
        logger=logger,
        use_cache=not typer.get_app().pretty_exceptions_short
    )


def diarize_file_wrapper(
    audio_path: Path,
    command_name: str,
    pipeline: Any,
    num_speakers: Optional[int] = None,
    device: Optional[str] = None,
) -> tuple[DiarizationResult, Dict[str, Any]]:
    """
    Diarizes an audio or video file.

    Wrapper around processor_diarize_file for compatibility.
    """
    return processor_diarize_file(
        audio_path,
        pipeline,
        num_speakers=num_speakers,
        device=device,
        use_cache=not typer.get_app().pretty_exceptions_short
    )


def show_cache_info(logger: logging.Logger) -> None:
    """
    Muestra información sobre el estado de las cachés.

    Args:
        logger: Logger para registrar la información
    """
    pipeline_cache = get_pipeline_cache_info()
    logger.info("== Estadísticas de caché de pipelines ==")
    for pipeline_type, info in pipeline_cache.items():
        logger.info(f"Pipeline de {pipeline_type}:")
        logger.info(f"  Hits: {info['hits']}, Misses: {info['misses']}")
        logger.info(f"  Tamaño actual: {info['currsize']}/{info['maxsize']}")
    audio_cache = get_audio_cache_info()
    logger.info("== Estadísticas de caché de audio ==")
    logger.info(f"Entradas: {audio_cache['entries']}/{audio_cache['max_entries']}")
    logger.info(f"Tamaño: {audio_cache['size_mb']:.2f}MB/{audio_cache['max_size_mb']:.2f}MB ({audio_cache['usage_percent']:.1f}%)")

# --- CLI Commands ---

@app.command()
def transcribe(
    audio_inputs: List[str] = typer.Argument(..., help=HELP_AUDIO_INPUTS),
    model: str = typer.Option(DEFAULT_MODEL, help=HELP_MODEL),
    task: Task = typer.Option(DEFAULT_TASK, help=HELP_TASK),
    lang: Optional[str] = typer.Option(DEFAULT_LANGUAGE, "--lang", "-l", help=HELP_LANG),
    chunk_length: int = typer.Option(DEFAULT_CHUNK_LENGTH, help=HELP_CHUNK_LENGTH),
    batch_size: int = typer.Option(DEFAULT_BATCH_SIZE, help=HELP_BATCH_SIZE),
    attn_type: str = typer.Option(DEFAULT_ATTN_TYPE, help=HELP_ATTN_TYPE),
    device: Device = typer.Option(Device.auto, help=HELP_DEVICE),
    formats: List[str] = typer.Option(DEFAULT_FORMATS["transcribe"], "--format", "-f", help=HELP_FORMATS, case_sensitive=False),
    log_level: LogLevel = typer.Option(DEFAULT_LOG_LEVEL, "--log-level", "-log", help=HELP_LOG_LEVEL),
    log_file: Optional[str] = typer.Option(None, help=HELP_LOG_FILE),
    show_formats: bool = typer.Option(False, "--show-formats", help=HELP_SHOW_FORMATS),
    no_cache: bool = typer.Option(False, "--no-cache", help="Desactiva el uso de caché"),
):
    """Transcribe audio/video files."""
    processed_files = setup_command(log_level, log_file, show_formats, audio_inputs)
    if not processed_files:
        return

    logger = logging.getLogger("wx3.transcribe")
    device_str = resolve_device(device)
    pipeline = get_transcription_pipeline(model, device_str, attn_type)
    logger.info(MSG_PROCESSING_FILES, len(processed_files))

    for file_idx, file_path in enumerate(processed_files, start=1):
        try:
            logger.info(MSG_PROCESSING_FILE, file_idx, len(processed_files), file_path.name)
            result = transcribe_file_wrapper(
                audio_path=file_path,
                command_name="transcribe",
                pipeline=pipeline,
                task=task.value,
                language=lang,
                chunk_length=chunk_length,
                batch_size=batch_size,
                device=device_str,
            )

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

    show_loading_times(logger)
    if not no_cache:
        show_cache_info(logger)


@app.command()
def diarize(
    audio_inputs: List[str] = typer.Argument(..., help=HELP_AUDIO_INPUTS),
    hf_token: str = typer.Option(..., help=HELP_HF_TOKEN, envvar="HF_TOKEN"),
    num_speakers: Optional[int] = typer.Option(None, help=HELP_NUM_SPEAKERS),
    device: Device = typer.Option(Device.auto, help=HELP_DEVICE),
    formats: List[str] = typer.Option(DEFAULT_FORMATS["diarize"], "--format", "-f", help=HELP_FORMATS, case_sensitive=False),
    log_level: LogLevel = typer.Option(DEFAULT_LOG_LEVEL, "--log-level", "-log", help=HELP_LOG_LEVEL),
    log_file: Optional[str] = typer.Option(None, help=HELP_LOG_FILE),
    show_formats: bool = typer.Option(False, "--show-formats", help=HELP_SHOW_FORMATS),
    no_cache: bool = typer.Option(False, "--no-cache", help="Desactiva el uso de caché"),
):
    """Diarize audio/video files."""
    processed_files = setup_command(log_level, log_file, show_formats, audio_inputs)
    if not processed_files:
        return

    logger = logging.getLogger("wx3.diarize")
    device_str = resolve_device(device)
    pipeline = get_diarization_pipeline(hf_token, device_str)
    logger.info(MSG_PROCESSING_FILES, len(processed_files))

    for file_idx, file_path in enumerate(processed_files, start=1):
        try:
            logger.info(MSG_PROCESSING_FILE, file_idx, len(processed_files), file_path.name)
            diar_result, _ = diarize_file_wrapper(
                audio_path=file_path,
                command_name="diarize",
                pipeline=pipeline,
                num_speakers=num_speakers,
                device=device_str,
            )
            diar_info = format_diarization_result(str(file_path), diar_result)
            diar_result_dict = {"speakers": diar_info["speakers"]}
            base_path = get_output_base_path(file_path, "diarize")
            logger.info(MSG_SAVING_RESULTS, file_path.name)

            for fmt in formats:
                fmt = fmt.lower()
                if fmt == "json":
                    save_json(base_path, diar_result_dict) # Guardar el diccionario formateado
                    logger.info(MSG_FILE_SAVED, "JSON", base_path.with_suffix('.json').name)
                else:
                    logger.warning(MSG_UNKNOWN_FORMAT, fmt)
        except Exception as exc:
            logger.error(MSG_ERROR_PROCESSING, file_path.name, str(exc))
            logger.exception(exc)

    show_loading_times(logger)
    if not no_cache:
        show_cache_info(logger)


@app.command()
def process(
    audio_inputs: List[str] = typer.Argument(..., help=HELP_AUDIO_INPUTS),
    model: str = typer.Option(DEFAULT_MODEL, help=HELP_MODEL),
    task: Task = typer.Option(DEFAULT_TASK, help=HELP_TASK),
    lang: Optional[str] = typer.Option(DEFAULT_LANGUAGE, "--lang", "-l", help=HELP_LANG),
    chunk_length: int = typer.Option(DEFAULT_CHUNK_LENGTH, help=HELP_CHUNK_LENGTH),
    batch_size: int = typer.Option(DEFAULT_BATCH_SIZE, help=HELP_BATCH_SIZE),
    attn_type: str = typer.Option(DEFAULT_ATTN_TYPE, help=HELP_ATTN_TYPE),
    num_speakers: Optional[int] = typer.Option(None, help=HELP_NUM_SPEAKERS),
    hf_token: str = typer.Option(..., help=HELP_HF_TOKEN, envvar="HF_TOKEN"), # Added envvar
    device: Device = typer.Option(Device.auto, help=HELP_DEVICE),
    formats: List[str] = typer.Option(
        DEFAULT_FORMATS["process"], "--format", "-f",
        help=HELP_FORMATS, case_sensitive=False
    ),
    log_level: LogLevel = typer.Option(
        DEFAULT_LOG_LEVEL, "--log-level", "-log", help=HELP_LOG_LEVEL
    ),
    log_file: Optional[str] = typer.Option(None, help=HELP_LOG_FILE),
    show_formats: bool = typer.Option(False, "--show-formats", help=HELP_SHOW_FORMATS),
    speaker_names: Optional[str] = typer.Option(
        None, help="Comma-separated list of speaker names to replace SPEAKER_xx"
    ),
    no_cache: bool = typer.Option(False, "--no-cache", help="Desactiva el uso de caché"),
):
    """
    Combined pipeline: diarization → transcription → alignment/export.
    Reuses audio loaded in the diarization stage to avoid a second read.
    """
    processed_files = setup_command(log_level, log_file, show_formats, audio_inputs)
    if not processed_files:
        return

    logger = logging.getLogger("wx3.process")
    device_str = resolve_device(device)
    diar_pipeline = get_diarization_pipeline(hf_token, device_str)
    trans_pipeline = get_transcription_pipeline(model, device_str, attn_type)
    logger.info(MSG_PROCESSING_FILES, len(processed_files))
    speaker_names_list = None
    if speaker_names:
        speaker_names_list = [name.strip() for name in speaker_names.split(",")]

    for file_idx, file_path in enumerate(processed_files, start=1):
        try:
            logger.info(MSG_PROCESSING_FILE, file_idx, len(processed_files), file_path.name)
            process_file(
                file_path=file_path,
                diar_pipeline=diar_pipeline,
                trans_pipeline=trans_pipeline,
                task=task.value,
                language=lang,
                chunk_length=chunk_length,
                batch_size=batch_size,
                formats=formats,
                num_speakers=num_speakers,
                device_str=device_str,
                speaker_names=speaker_names_list,
                logger=logger,
                save_intermediate=True,
                use_cache=not no_cache
            )
        except Exception as exc:
            logger.error(MSG_ERROR_PROCESSING, file_path.name, exc)
            logger.exception(exc)

    show_loading_times(logger)
    if not no_cache:
        show_cache_info(logger)


@app.command()
def manage_cache(
    clear_all: bool = typer.Option(False, "--clear-all", help="Limpia todas las cachés"),
    clear_pipelines: bool = typer.Option(False, "--clear-pipelines", help="Limpia la caché de pipelines"),
    clear_audio: bool = typer.Option(False, "--clear-audio", help="Limpia la caché de audio"),
    show_info: bool = typer.Option(True, "--info/--no-info", help="Muestra información de caché"),
    max_audio_size_mb: Optional[int] = typer.Option(None, "--max-audio-size", help="Configura el tamaño máximo de caché de audio en MB"),
    max_audio_entries: Optional[int] = typer.Option(None, "--max-audio-entries", help="Configura el número máximo de entradas en caché de audio"),
    log_level: LogLevel = typer.Option(DEFAULT_LOG_LEVEL, "--log-level", "-log", help=HELP_LOG_LEVEL),
):
    """
    Gestiona las cachés de la aplicación.

    Permite limpiar y configurar las cachés de pipelines y audio.
    """
    setup_logging(log_level, None)
    logger = logging.getLogger("wx3.cache")
    if clear_all or clear_pipelines:
        clear_pipeline_cache()
        logger.info("Caché de pipelines limpiada")
    if clear_all or clear_audio:
        clear_audio_cache()
        logger.info("Caché de audio limpiada")

    # Configurar caché de audio si se especifican opciones
    if max_audio_size_mb is not None:
        from input_media import set_max_cache_size
        set_max_cache_size(max_audio_size_mb * 1024 * 1024)
        logger.info(f"Tamaño máximo de caché de audio configurado a {max_audio_size_mb}MB")
    if max_audio_entries is not None:
        from input_media import set_max_cache_entries
        set_max_cache_entries(max_audio_entries)
        logger.info(f"Número máximo de entradas en caché de audio configurado a {max_audio_entries}")
    if show_info:
        show_cache_info(logger)


if __name__ == "__main__":
    app()