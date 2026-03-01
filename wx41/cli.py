import typer
from pathlib import Path
from typing import Optional
from wx41.context import PipelineConfig
from wx41.pipeline import MediaOrchestrator
from wx41.steps.transcribe import TranscribeConfig

app = typer.Typer()

@app.command()
def main(
    src: Path = typer.Argument(...),
    aai_key: Optional[str] = typer.Option(None, '--aai-key'),
    backend: str = typer.Option('assemblyai', '--backend'),
) -> None:
    settings = {'transcribe': TranscribeConfig(backend=backend, api_key=aai_key)}
    config = PipelineConfig(settings=settings)
    orchestrator = MediaOrchestrator(config, [])
    orchestrator.run(src)

if __name__ == '__main__':
    app()
