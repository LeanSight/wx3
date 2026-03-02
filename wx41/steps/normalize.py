import dataclasses
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict

from wx41.context import PipelineContext
from wx41.audio_normalize import normalize_lufs


@dataclass(frozen=True)
class NormalizeConfig:
    target_lufs: float = -23.0
    output_keys: tuple = ("normalized",)


def normalize_step(ctx: PipelineContext, config: NormalizeConfig) -> PipelineContext:
    audio = ctx.src
    out_path = audio.parent / f"{audio.stem}_normalized.m4a"
    normalize_lufs(audio, out_path, progress_callback=ctx.step_progress)
    new_outputs = {**ctx.outputs, config.output_keys[0]: out_path}
    return dataclasses.replace(ctx, outputs=new_outputs)


def normalize_output_fn(ctx: PipelineContext, config: NormalizeConfig) -> Dict[str, Path]:
    audio = ctx.src
    out_path = audio.parent / f"{audio.stem}_normalized.m4a"
    return {config.output_keys[0]: out_path}


from wx41.steps import register_step
register_step("normalize", normalize_step, normalize_output_fn)
