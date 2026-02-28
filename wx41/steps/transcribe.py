import dataclasses

from wx41.context import PipelineContext
from wx41.step_common import timer
from wx41.transcribe_aai import transcribe_assemblyai
from wx41.transcribe_wx3 import transcribe_with_whisper


@timer("transcribe")
def transcribe_step(ctx: PipelineContext) -> PipelineContext:
    audio = ctx.enhanced if ctx.enhanced is not None else ctx.src

    if ctx.transcribe_backend == "assemblyai":
        txt_path, json_path = transcribe_assemblyai(
            audio,
            ctx.language,
            ctx.speakers,
            progress_callback=ctx.step_progress,
        )
    elif ctx.transcribe_backend == "whisper":
        txt_path, json_path = transcribe_with_whisper(
            audio,
            lang=ctx.language,
            speakers=ctx.speakers,
            hf_token=ctx.hf_token,
            device=ctx.device,
            whisper_model=ctx.whisper_model,
        )
    else:
        raise RuntimeError(
            f"Unknown transcribe_backend: {ctx.transcribe_backend!r}. "
            "Expected 'assemblyai' or 'whisper'."
        )

    return dataclasses.replace(ctx, transcript_txt=txt_path, transcript_json=json_path)
