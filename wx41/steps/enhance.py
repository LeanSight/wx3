import dataclasses
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict

from wx41.context import PipelineContext
from wx41.audio_enhance import apply_clearvoice
from wx41.steps import register_step, predict_output_path


@dataclass(frozen=True)
class EnhanceConfig:
    model_path: Optional[Path] = None
    output_keys: tuple = ("enhanced",)
    enabled: bool = True


def enhance_step(ctx: PipelineContext, config: EnhanceConfig) -> PipelineContext:
    if not config.enabled:
        return ctx
    audio = ctx.outputs.get("normalized") or ctx.src
    out_path = predict_output_path(ctx.src, "enhance", config.output_keys[0])
    apply_clearvoice(
        audio,
        out_path,
        model_path=config.model_path,
        progress_callback=ctx.step_progress,
    )
    new_outputs = {**ctx.outputs, config.output_keys[0]: out_path}
    return dataclasses.replace(ctx, outputs=new_outputs)


def enhance_output_fn(ctx: PipelineContext, config: EnhanceConfig) -> Dict[str, Path]:
    if not config.enabled:
        return {}
    out_path = predict_output_path(ctx.src, "enhance", config.output_keys[0])
    return {config.output_keys[0]: out_path}


register_step(
    "enhance",
    enhance_step,
    enhance_output_fn,
    optional=True,
    description="Enhance audio clarity using ClearVoice",
    config_class=EnhanceConfig,
    needs_audio_fixture=True,
)
