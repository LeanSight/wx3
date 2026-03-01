import dataclasses
from dataclasses import dataclass
from typing import Optional, Tuple, Dict
from pathlib import Path

from wx41.context import PipelineContext

@dataclass(frozen=True)
class TranscribeConfig:
    backend: str = 'assemblyai'
    api_key: Optional[str] = None
    language: Optional[str] = None
    speakers: Optional[int] = None

def transcribe_step(ctx: PipelineContext, config: TranscribeConfig) -> PipelineContext:
    audio = ctx.outputs.get('enhanced') or ctx.outputs.get('normalized') or ctx.src
    from wx41.steps.transcribe import transcribe_assemblyai
    txt, jsn = transcribe_assemblyai(audio, config)
    new_outputs = {**ctx.outputs, 'transcript_txt': txt, 'transcript_json': jsn}
    return dataclasses.replace(ctx, outputs=new_outputs)

def transcribe_assemblyai(audio: Path, config: TranscribeConfig) -> Tuple[Path, Path]:
    return Path('none.txt'), Path('none.json')
