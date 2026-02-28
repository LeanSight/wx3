"""
Transcribe step - transcribes audio using AssemblyAI or Whisper.
"""

import dataclasses
import time

from wx4.context import PipelineContext
from wx4.transcribe_aai import transcribe_assemblyai
from wx4.transcribe_wx3 import transcribe_with_whisper


def transcribe_step(ctx: PipelineContext) -> PipelineContext:
    """
    Transcribe audio using the backend specified in ctx.transcribe_backend.

    - "assemblyai" (default): calls transcribe_assemblyai (requires ASSEMBLY_AI_KEY)
    - "whisper": calls transcribe_with_whisper (local, requires hf_token for diarization)

    Uses ctx.enhanced if set, otherwise ctx.src.
    Raises RuntimeError for unknown backends.
    """
    t0 = time.time()
    audio = ctx.enhanced if ctx.enhanced is not None else ctx.src

    if ctx.transcribe_backend == "assemblyai":
        txt_path, json_path = transcribe_assemblyai(audio, ctx.language, ctx.speakers)
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

    return dataclasses.replace(
        ctx,
        transcript_txt=txt_path,
        transcript_json=json_path,
        timings={**ctx.timings, "transcribe": time.time() - t0},
    )
