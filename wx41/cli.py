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
    aai_key: Optional[str] = typer.Option(None, "--aai-key"),
    hf_token: Optional[str] = typer.Option(None, "--hf-token"),
) -> None:
    config = PipelineConfig(
        force=force,
        assembly_ai_key=aai_key,
        hf_token=hf_token,
    )
    orchestrator = MediaOrchestrator(config, [])
    orchestrator.run(src)


if __name__ == "__main__":
    app()
