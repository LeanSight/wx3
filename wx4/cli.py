"""
Typer + Rich CLI for wx4 pipeline.
"""

from pathlib import Path
from typing import List, Optional

import typer
from rich import box
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from wx4.context import PipelineConfig, PipelineContext
from wx4.pipeline import Pipeline, build_steps
from wx4.speakers import parse_speakers_map

_CV_MODEL = "MossFormer2_SE_48K"

app = typer.Typer(add_completion=False, no_args_is_help=True)
console = Console()


class RichProgressCallback:
    """Satisfies PipelineCallback via duck typing."""

    def __init__(self, progress: Progress) -> None:
        self._p = progress
        self._overall = None
        self._step_task = None

    def on_pipeline_start(self, step_names: List[str]) -> None:
        self._overall = self._p.add_task("Pipeline", total=len(step_names))

    def on_step_start(self, name: str, ctx: PipelineContext) -> None:
        self._step_task = self._p.add_task(f"  {name}", total=None)

    def on_step_progress(self, name: str, done: int, total: int) -> None:
        """Update the current step's progress bar with chunk-level granularity."""
        if self._step_task is not None:
            self._p.update(self._step_task, total=total, completed=done)

    def on_step_end(self, name: str, ctx: PipelineContext) -> None:
        if self._step_task is not None:
            self._p.update(self._step_task, visible=False)
            self._step_task = None
        if self._overall is not None:
            self._p.update(self._overall, advance=1)

    def on_step_skipped(self, name: str, ctx: PipelineContext) -> None:
        self._p.console.print(f"  [dim]{name}: already done, skipping[/dim]")
        if self._overall is not None:
            self._p.update(self._overall, advance=1)

    def on_pipeline_end(self, ctx: PipelineContext) -> None:
        pass


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
        "--whisper-hf-token",
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

    if api_key:
        import os

        os.environ["ASSEMBLY_AI_KEY"] = api_key

    speaker_names = parse_speakers_map(speakers_map)
    config = PipelineConfig(
        skip_normalize=skip_normalize,
        skip_enhance=skip_enhance,
        videooutput=videooutput,
        compress_ratio=compress,
    )
    steps = build_steps(config)

    cv = None
    if not skip_enhance:
        from clearvoice import ClearVoice

        console.print(f"Loading {_CV_MODEL}...")
        cv = ClearVoice(task="speech_enhancement", model_names=[_CV_MODEL])

    results = []
    with Progress(
        SpinnerColumn(),
        TextColumn("{task.description}"),
        TimeElapsedColumn(),
        BarColumn(),
        transient=True,
        console=console,
    ) as progress:
        cb = RichProgressCallback(progress)
        pipeline = Pipeline(steps, callbacks=[cb])

        for file_str in files:
            src = Path(file_str)
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
