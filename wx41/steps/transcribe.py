import dataclasses
from dataclasses import dataclass
from typing import Optional, Tuple, Dict
from pathlib import Path

from wx41.context import PipelineContext
from wx41.step_common import timer
from wx41.transcribe_aai import transcribe_assemblyai
from wx41.transcribe_whisper import transcribe_whisper

@dataclass(frozen=True)
class TranscribeConfig:
    backend: str = 'assemblyai'
    api_key: Optional[str] = None
    language: Optional[str] = None
    speakers: Optional[int] = None
    model: str = 'openai/whisper-base'
    output_keys: Tuple[str, str] = ('transcript_txt', 'transcript_json')
    enabled: bool = True

@timer('transcribe')
def transcribe_step(ctx: PipelineContext, config: TranscribeConfig) -> PipelineContext:
    if not config.enabled:
        return ctx
    audio = ctx.outputs.get('enhanced') or ctx.outputs.get('normalized') or ctx.src
    
    from wx41.steps import predict_output_path
    txt_path = predict_output_path(audio, "transcribe", config.output_keys[0])
    jsn_path = predict_output_path(audio, "transcribe", config.output_keys[1])
    
    if config.backend == 'assemblyai':
        txt, jsn = transcribe_assemblyai(
            audio, 
            api_key=config.api_key, 
            lang=config.language, 
            speakers=config.speakers,
            progress_callback=ctx.step_progress,
            txt_path=txt_path,
            json_path=jsn_path
        )
    elif config.backend == 'whisper':
        txt, jsn = transcribe_whisper(
            audio,
            api_key=config.api_key,
            lang=config.language,
            speakers=config.speakers,
            progress_callback=ctx.step_progress,
            model=config.model,
            txt_path=txt_path,
            json_path=jsn_path
        )
    else:
        raise RuntimeError(f'Backend {config.backend} not implemented yet')

    new_outputs = {**ctx.outputs, config.output_keys[0]: txt, config.output_keys[1]: jsn}
    return dataclasses.replace(ctx, outputs=new_outputs)


def transcribe_output_fn(ctx: PipelineContext, config: TranscribeConfig) -> Dict[str, Path]:
    if not config.enabled:
        return {}
    audio = ctx.outputs.get('enhanced') or ctx.outputs.get('normalized') or ctx.src
    from wx41.steps import predict_output_path
    txt_path = predict_output_path(audio, "transcribe", config.output_keys[0])
    jsn_path = predict_output_path(audio, "transcribe", config.output_keys[1])
    return {config.output_keys[0]: txt_path, config.output_keys[1]: jsn_path}


from wx41.steps import register_step
register_step(
    "transcribe", 
    transcribe_step, 
    transcribe_output_fn,
    optional=False,
    description="Transcribe audio to text and JSON timestamps",
    config_class=TranscribeConfig
)
