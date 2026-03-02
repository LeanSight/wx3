import typer
from pathlib import Path
from typing import Optional
from wx41.context import PipelineConfig
from wx41.pipeline import MediaOrchestrator
from wx41.steps.transcribe import TranscribeConfig

app = typer.Typer()

@app.command()
def main(
    src: Path = typer.Argument(..., help="Audio file to process"),
    aai_key: Optional[str] = typer.Option(None, '--aai-key', help="AssemblyAI API key"),
    backend: str = typer.Option('assemblyai', '--backend', help="Transcription backend: assemblyai or whisper"),
    dry_run: bool = typer.Option(False, '--dry-run', help="Simulate execution without running steps"),
    force: bool = typer.Option(False, '--force', help="Force re-execution even if outputs exist"),
    state_path: Optional[Path] = typer.Option(None, '--state-path', help="Path to save/restore state for interruption"),
) -> None:
    settings = {'transcribe': TranscribeConfig(backend=backend, api_key=aai_key)}
    config = PipelineConfig(settings=settings, force=force)
    orchestrator = MediaOrchestrator(config, [], state_path=state_path)
    orchestrator.run(src, dry_run=dry_run)

if __name__ == '__main__':
    app()
