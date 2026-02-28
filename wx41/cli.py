from pathlib import Path
from typing import Optional
import typer
from wx41.context import PipelineConfig
from wx41.pipeline import MediaOrchestrator
from wx41.steps.transcribe import TranscribeConfig

app = typer.Typer()


@app.command()
def main(
    src: Path = typer.Argument(...),
    force: bool = typer.Option(False, "--force"),
    compress: Optional[float] = typer.Option(None, "--compress"),
    skip_normalize: bool = typer.Option(False, "--no-normalize"),
    skip_enhance: bool = typer.Option(False, "--no-enhance"),
    # Parámetros del contexto/pipeline general
    language: Optional[str] = typer.Option(None, "--language"),
    speakers: Optional[int] = typer.Option(None, "--speakers"),
    # El CLI compone los parámetros que publica el step
    backend: str = typer.Option("assemblyai", "--backend"),
    aai_key: Optional[str] = typer.Option(None, "--aai-key", envvar="ASSEMBLY_AI_KEY"),
    hf_token: Optional[str] = typer.Option(None, "--hf-token", envvar="HF_TOKEN"),
    whisper_model: str = typer.Option("openai/whisper-large-v3", "--whisper-model"),
    device: str = typer.Option("auto", "--device"),
) -> None:
    # Construimos la configuración modular
    transcribe_cfg = TranscribeConfig(
        backend=backend,
        api_key=aai_key,
        hf_token=hf_token,
        whisper_model=whisper_model,
        device=device,
    )

    config = PipelineConfig(
        force=force,
        compress_ratio=compress,
        skip_normalize=skip_normalize,
        skip_enhance=skip_enhance,
        language=language,
        speakers=speakers,
        transcribe=transcribe_cfg,
    )
    
    orchestrator = MediaOrchestrator(config, [])
    
    # El MediaOrchestrator no necesita saber nada de los parámetros de los steps
    # Los recibe dentro de su config modular
    orchestrator.run(src)


if __name__ == "__main__":
    app()
