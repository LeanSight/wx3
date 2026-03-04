import dataclasses
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict

from wx41.context import PipelineContext
from wx41.steps import register_step, predict_output_path
from wx41.video_gen import generate_black_video


@dataclass(frozen=True)
class BlackVideoConfig:
    width: int = 1920
    height: int = 1080
    fps: int = 24
    enabled: bool = True
    output_keys: tuple = ("video",)


def black_video_step(ctx: PipelineContext, config: BlackVideoConfig) -> PipelineContext:
    if not config.enabled:
        return ctx

    audio = ctx.outputs.get("enhanced") or ctx.outputs.get("normalized") or ctx.src
    out_path = predict_output_path(ctx.src, "black_video", config.output_keys[0])

    generate_black_video(
        audio,
        out_path,
        width=config.width,
        height=config.height,
        fps=config.fps,
        progress_callback=ctx.step_progress,
    )

    new_outputs = {**ctx.outputs, config.output_keys[0]: out_path}
    return dataclasses.replace(ctx, outputs=new_outputs)


def black_video_output_fn(
    ctx: PipelineContext, config: BlackVideoConfig
) -> Dict[str, Path]:
    if not config.enabled:
        return {}
    out_path = predict_output_path(ctx.src, "black_video", config.output_keys[0])
    return {config.output_keys[0]: out_path}


register_step(
    "black_video",
    black_video_step,
    black_video_output_fn,
    optional=True,
    description="Generate a black video synchronized with audio",
    config_class=BlackVideoConfig,
    input_media_type="video",
)
