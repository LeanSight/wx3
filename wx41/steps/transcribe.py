import dataclasses
from dataclasses import dataclass
from typing import Optional, Tuple, Dict
from pathlib import Path

from wx41.context import PipelineContext
from wx41.step_common import timer
from wx41.transcribe_aai import transcribe_assemblyai

@dataclass(frozen=True)
class TranscribeConfig:
    backend: str = 'assemblyai'
    api_key: Optional[str] = None
    language: Optional[str] = None
    speakers: Optional[int] = None

@timer('transcribe')
def transcribe_step(ctx: PipelineContext, config: TranscribeConfig) -> PipelineContext:
    audio = ctx.outputs.get('enhanced') or ctx.outputs.get('normalized') or ctx.src
    
    if config.backend == 'assemblyai':
        txt, jsn = transcribe_assemblyai(
            audio, 
            api_key=config.api_key, 
            lang=config.language, 
            speakers=config.speakers,
            progress_callback=ctx.step_progress
        )
    else:
        raise RuntimeError(f'Backend {config.backend} not implemented yet')

    new_outputs = {**ctx.outputs, 'transcript_txt': txt, 'transcript_json': jsn}
    return dataclasses.replace(ctx, outputs=new_outputs)
