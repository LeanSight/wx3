"""
Typer + Rich CLI for wx4 pipeline.
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import typer
from rich import box
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table
from rich.console import Group
from rich.text import Text

from wx4.context import PipelineConfig, PipelineContext
from wx4.pipeline import Pipeline, build_steps
from wx4.speakers import parse_speakers_map

_CV_MODEL = "MossFormer2_SE_48K"

app = typer.Typer(add_completion=False, no_args_is_help=True)
console = Console(markup=True, force_terminal=True)


def _make_progress(console: Console) -> Progress:
    """Create Progress widget with all required columns."""
    return Progress(
        SpinnerColumn(),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
    )


def _get_secret(
    arg_value: Optional[str], env_var: str, required: bool = False
) -> Optional[str]:
    """
    Read secret with priority: argument > env var > error/None.
    """
    if arg_value:
        return arg_value
    value = os.environ.get(env_var)
    if value:
        return value
    if required:
        raise typer.BadParameter(
            f"Neither provided via argument nor set in {env_var} environment variable"
        )
    return None


# Import ffprobe for media detection
import ffmpeg

# Extension fallback para archivos de audio/video validos
_AUDIO_EXTENSIONS = {".mp4", ".mp3", ".m4a", ".wav", ".avi", ".mov", ".flac"}


def _is_intermediate_file(path: Path) -> bool:
    """Detecta archivos intermedios generados por el pipeline."""
    from wx4.context import INTERMEDIATE_PATTERNS

    return any(path.name.endswith(p) for p in INTERMEDIATE_PATTERNS)


def _has_video_stream(path: Path) -> bool | None:
    """Usa ffprobe para detectar si tiene stream de video. None si error."""
    try:
        data = ffmpeg.probe(str(path))
        return any(s["codec_type"] == "video" for s in data["streams"])
    except Exception:
        return None


def _is_processable_file(path: Path) -> bool:
    """Es archivo de audio/video valido? (ffprobe para detectar tipo)."""
    if not path.is_file():
        return False
    if _is_intermediate_file(path):
        return False
    result = _has_video_stream(path)
    if result is None:
        return path.suffix.lower() in _AUDIO_EXTENSIONS
    return True


def _expand_paths(paths: List[str]) -> List[Path]:
    """Expande paths - directorios a archivos de audio/video validos (recursivo)."""
    expanded = []
    for p in paths:
        src = Path(p)
        if src.is_dir():
            for f in src.rglob("*"):  # recursive glob
                if f.is_file() and _is_processable_file(f):
                    expanded.append(f)
        elif src.is_file():
            expanded.append(src)
    return sorted(expanded, key=lambda x: x.name)


class RichProgressCallback:
    """Hierarchical pipeline view with file name and step states."""

    # ASCII characters for Windows compatibility
    _PENDING = "o"
    _RUNNING = ">"
    _COMPLETE = "x"
    _SKIPPED = "-"

    def __init__(self, console: Console, progress: Progress) -> None:
        self._console = console
        self._progress = progress
        self._current_file: Path | None = None
        self._step_names: List[str] = []
        self._step_states: Dict[str, str] = {}
        self._current_step: str | None = None
        self._progress_task: TaskID | None = None
        self._progress_completed: Dict[str, int] = {}
        self._live = None

    def _render_tree(self) -> Any:
        """Render hierarchical view as indented tree."""
        lines = []
        if self._current_file:
            lines.append(f"[bold]{self._current_file.name}[/bold]")
        for name in self._step_names:
            state = self._step_states.get(name, "pending")
            if state == "running":
                icon = f"[cyan]{self._RUNNING}[/cyan]"
                percent = self._progress_completed.get(name, 0)
                name_with_percent = f"{name} {percent}%" if percent > 0 else name
            elif state == "complete":
                icon = f"[green]{self._COMPLETE}[/green]"
                name_with_percent = name
            elif state == "skipped":
                icon = f"[dim]{self._SKIPPED}[/dim]"
                name_with_percent = name
            else:
                icon = f"[dim]{self._PENDING}[/dim]"
                name_with_percent = name
            lines.append(f"  {icon} {name_with_percent}")
        tree = Text.from_markup("\n".join(lines))
        if self._progress_task is not None:
            return Group(tree, self._progress)
        return tree

    def on_pipeline_start(self, step_names: List[str], ctx: PipelineContext) -> None:
        self._current_file = ctx.src
        self._step_names = step_names
        self._step_states = {name: "pending" for name in step_names}

        # Start Live for smooth updates
        self._live = Live(
            self._render_tree(),
            console=self._console,
            refresh_per_second=4,
            transient=False,
        )
        self._live.start()

    def on_step_start(self, name: str, ctx: PipelineContext) -> None:
        self._current_step = name
        self._step_states[name] = "running"
        self._progress_task = self._progress.add_task("", total=100)
        if self._live:
            self._live.update(self._render_tree())

    def on_step_progress(self, name: str, done: int, total: int) -> None:
        if total > 0:
            percent = int(done * 100 / total)
            self._progress_completed[name] = percent
            if self._progress_task is not None:
                self._progress.update(self._progress_task, total=total, completed=done)
            if self._live:
                self._live.update(self._render_tree())

    def on_step_end(self, name: str, ctx: PipelineContext) -> None:
        self._step_states[name] = "complete"
        self._current_step = None
        if self._progress_task is not None:
            self._progress.update(self._progress_task, visible=False)
            self._progress_task = None
        if self._live:
            self._live.update(self._render_tree())

    def on_step_skipped(self, name: str, ctx: PipelineContext) -> None:
        self._step_states[name] = "skipped"
        if self._live:
            self._live.update(self._render_tree())

    def on_pipeline_end(self, ctx: PipelineContext) -> None:
        if self._live:
            self._live.update(self._render_tree())
            self._live.stop()
            self._live = None


@app.command()
def main(
    ctx: typer.Context,
    files: Optional[List[str]] = typer.Argument(
        default=None, help="Audio/video files to process"
    ),
    language: Optional[str] = typer.Option(
        None, "--language", "-l", help="Language code (e.g. es, en). Default: auto"
    ),
    speakers: Optional[int] = typer.Option(
        None, "--speakers", "-s", help="Expected number of speakers. Default: auto"
    ),
    srt_mode: str = typer.Option(
        "speaker-only",
        "--srt-mode",
        help="SRT grouping mode: 'speaker-only' or 'sentences'",
    ),
    speakers_map: Optional[str] = typer.Option(
        None, "--speakers-map", help="Speaker name map, e.g. 'A=Marcel,B=Agustin'"
    ),
    skip_normalize: bool = typer.Option(
        False, "--no-normalize", help="Skip LUFS audio normalization"
    ),
    skip_enhance: bool = typer.Option(
        False, "--no-enhance", help="Skip ClearVoice audio enhancement"
    ),
    force: bool = typer.Option(False, "--force", help="Force re-process cached files"),
    videooutput: bool = typer.Option(
        False, "--video-output", help="Generate output MP4"
    ),
    api_key: Optional[str] = typer.Option(
        None,
        "--assemblyai-api-key",
        help="AssemblyAI API key (or set ASSEMBLY_AI_KEY env var)",
    ),
    compress: Optional[float] = typer.Option(
        None,
        "--compress",
        help="Compress source video to ratio (e.g. --compress 0.4 = 40%% of original size)",
    ),
    backend: str = typer.Option(
        "assemblyai", "--backend", help="Transcription backend: assemblyai or whisper"
    ),
    hf_token: Optional[str] = typer.Option(
        None,
        "--pyannote-hf-token",
        help="HuggingFace token for PyAnnote diarization (whisper backend)",
    ),
    device: str = typer.Option(
        "auto",
        "--whisper-device",
        help="Compute device: auto, cpu, cuda, mps (whisper backend)",
    ),
    whisper_model: str = typer.Option(
        "openai/whisper-large-v3",
        "--whisper-model",
        help="Whisper model identifier (whisper backend)",
    ),
) -> None:
    if not files:
        typer.echo(ctx.get_help())
        raise typer.Exit()

    files = _expand_paths(files)
    if not files:
        console.print("No se encontraron archivos de audio/video para procesar")
        raise typer.Exit()

    api_key = _get_secret(api_key, "ASSEMBLY_AI_KEY", required=True)
    if api_key:
        os.environ["ASSEMBLY_AI_KEY"] = api_key

    speaker_names = parse_speakers_map(speakers_map)
    config = PipelineConfig(
        skip_normalize=skip_normalize,
        skip_enhance=skip_enhance,
        videooutput=videooutput,
        compress_ratio=compress,
    )
    steps = build_steps(config)

    hf_token = _get_secret(hf_token, "HF_TOKEN")

    cv = None
    if not skip_enhance:
        from clearvoice import ClearVoice

        console.print(f"Loading {_CV_MODEL}...")
        cv = ClearVoice(task="speech_enhancement", model_names=[_CV_MODEL])

    results = []
    # Progress para step progress
    progress = _make_progress(console)
    cb = RichProgressCallback(console, progress)
    pipeline = Pipeline(steps, callbacks=[cb])

    for src in files:
        if not src.exists():
            console.print(f"File not found: {src}")
            continue

        pipeline_ctx = PipelineContext(
            src=src,
            srt_mode=srt_mode,
            language=language,
            speakers=speakers,
            speaker_names=speaker_names,
            force=force,
            compress_ratio=compress if compress is not None else 0.40,
            cv=cv,
            transcribe_backend=backend,
            hf_token=hf_token,
            device=device,
            whisper_model=whisper_model,
        )
        pipeline_ctx = pipeline.run(pipeline_ctx)
        results.append(pipeline_ctx)

    table = Table(title="Summary", box=box.ASCII)
    table.add_column("File")
    table.add_column("SRT")
    table.add_column("Compressed")
    for result_ctx in results:
        srt_name = result_ctx.srt.name if result_ctx.srt else "N/A"
        compressed = (
            result_ctx.video_compressed.name if result_ctx.video_compressed else "-"
        )
        table.add_row(result_ctx.src.name, srt_name, compressed)
    console.print(table)


if __name__ == "__main__":
    app()
