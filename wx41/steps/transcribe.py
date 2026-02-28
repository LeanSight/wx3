import dataclasses
from dataclasses import dataclass
from typing import Optional

from wx41.context import PipelineContext
from wx41.step_common import timer
from wx41.transcribe_aai import transcribe_assemblyai
from wx41.transcribe_wx3 import transcribe_with_whisper


@dataclass(frozen=True)
class TranscribeConfig:
    backend: str = "assemblyai"
    api_key: Optional[str] = None
    hf_token: Optional[str] = None
    whisper_model: str = "openai/whisper-large-v3"
    device: str = "auto"


@timer("transcribe")
def transcribe_step(ctx: PipelineContext, config: TranscribeConfig) -> PipelineContext:
    audio = ctx.enhanced if ctx.enhanced is not None else ctx.src

    if config.backend == "assemblyai":
        txt_path, json_path = transcribe_assemblyai(
            audio,
            ctx.language,
            ctx.speakers,
            progress_callback=ctx.step_progress,
            api_key=config.api_key,
        )
    elif config.backend == "whisper":
        txt_path, json_path = transcribe_with_whisper(
            audio,
            lang=ctx.language,
            speakers=ctx.speakers,
            hf_token=config.hf_token,
            device=config.device,
            whisper_model=config.whisper_model,
        )
    else:
        raise RuntimeError(
            f"Unknown transcribe_backend: {config.backend!r}. "
            "Expected 'assemblyai' or 'whisper'."
        )

    return dataclasses.replace(ctx, transcript_txt=txt_path, transcript_json=json_path)
