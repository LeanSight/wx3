from pathlib import Path
from typing import Optional

import typer

from wx41.context import PipelineConfig
from wx41.pipeline import MediaOrchestrator

app = typer.Typer()


@app.command()
def main(
    src: Path = typer.Argument(...),
    backend: str = typer.Option("assemblyai", "--backend"),
    force: bool = typer.Option(False, "--force"),
    language: Optional[str] = typer.Option(None, "--language"),
    speakers: Optional[int] = typer.Option(None, "--speakers"),
) -> None:
    config = PipelineConfig()
    orchestrator = MediaOrchestrator(config, [])
    orchestrator.run(src)


if __name__ == "__main__":
    app()
