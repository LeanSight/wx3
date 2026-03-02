import dataclasses
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict

from wx41.context import PipelineContext
from wx41.audio_enhance import apply_clearvoice


@dataclass(frozen=True)
class EnhanceConfig:
    model_path: Optional[Path] = None
    output_keys: tuple = ("enhanced",)
    enabled: bool = True


def enhance_step(ctx: PipelineContext, config: EnhanceConfig) -> PipelineContext:
    if not config.enabled:
        return ctx
    audio = ctx.outputs.get("normalized") or ctx.src
    out_path = audio.parent / f"{audio.stem}_enhanced.m4a"
    apply_clearvoice(audio, out_path, model_path=config.model_path, progress_callback=ctx.step_progress)
    new_outputs = {**ctx.outputs, config.output_keys[0]: out_path}
    return dataclasses.replace(ctx, outputs=new_outputs)


def enhance_output_fn(ctx: PipelineContext, config: EnhanceConfig) -> Dict[str, Path]:
    if not config.enabled:
        return {}
    audio = ctx.outputs.get("normalized") or ctx.src
    out_path = audio.parent / f"{audio.stem}_enhanced.m4a"
    return {config.output_keys[0]: out_path}


from wx41.steps import register_step
register_step(
    "enhance", 
    enhance_step, 
    enhance_output_fn,
    optional=True,
    description="Enhance audio clarity using ClearVoice",
    config_class=EnhanceConfig
)
