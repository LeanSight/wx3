"""
Typer + Rich CLI for wx4 pipeline.
"""

from pathlib import Path
from typing import List, Optional

import typer
from rich import box
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

from clearvoice import ClearVoice

from wx4.context import PipelineContext
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
    files: Optional[List[str]] = typer.Argument(default=None, help="Audio/video files to process"),
    language: Optional[str] = typer.Option(
        None, "--language", "-l", help="Language code (e.g. es, en). Default: auto"
    ),
    speakers: Optional[int] = typer.Option(
        None, "--speakers", "-s", help="Expected number of speakers. Default: auto"
    ),
    srt_mode: str = typer.Option(
        "speaker-only", "--type", help="SRT mode: 'sentences' or 'speaker-only'"
    ),
    speakers_map: Optional[str] = typer.Option(
        None, "--speakers-map", help="Speaker name map, e.g. 'A=Marcel,B=Agustin'"
    ),
    skip_enhance: bool = typer.Option(False, "--skip-enhance", help="Skip enhancement step"),
    force: bool = typer.Option(False, "--force", help="Force re-process cached files"),
    videooutput: bool = typer.Option(False, "--videooutput", help="Generate output MP4"),
) -> None:
    if not files:
        typer.echo(ctx.get_help())
        raise typer.Exit()
    speaker_names = parse_speakers_map(speakers_map)
    steps = build_steps(skip_enhance=skip_enhance, videooutput=videooutput, force=force)

    cv = None
    if not skip_enhance:
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
                skip_enhance=skip_enhance,
                force=force,
                videooutput=videooutput,
                cv=cv,
            )
            pipeline_ctx = pipeline.run(pipeline_ctx)
            results.append(pipeline_ctx)

    table = Table(title="Summary", box=box.ASCII)
    table.add_column("File")
    table.add_column("SRT")
    for result_ctx in results:
        srt_name = result_ctx.srt.name if result_ctx.srt else "N/A"
        table.add_row(result_ctx.src.name, srt_name)
    console.print(table)


if __name__ == "__main__":
    app()
