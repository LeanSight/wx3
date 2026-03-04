import dataclasses
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict

from wx41.context import PipelineContext
from wx41.steps import register_step, predict_output_path
from wx41.video_gen import compress_video


@dataclass(frozen=True)
class CompressConfig:
    crf: int = 23
    preset: str = "medium"
    enabled: bool = True
    output_keys: tuple = ("video_compressed",)


def compress_step(ctx: PipelineContext, config: CompressConfig) -> PipelineContext:
    if not config.enabled:
        return ctx

    # Priority for Video source: video (from black_video) > src
    video = ctx.outputs.get("video") or ctx.src
    if not video or not video.exists():
        raise RuntimeError("Compress step requires a video input.")

    # Priority for Audio source: enhanced > normalized > src
    audio = ctx.outputs.get("enhanced") or ctx.outputs.get("normalized") or ctx.src

    out_path = predict_output_path(video, "compress", config.output_keys[0])

    compress_video(
        video,
        out_path,
        crf=config.crf,
        preset=config.preset,
        progress_callback=ctx.step_progress,
        audio_path=audio,
    )

    new_outputs = {**ctx.outputs, config.output_keys[0]: out_path}
    return dataclasses.replace(ctx, outputs=new_outputs)


def compress_output_fn(ctx: PipelineContext, config: CompressConfig) -> Dict[str, Path]:
    if not config.enabled:
        return {}
    out_path = predict_output_path(ctx.src, "compress", config.output_keys[0])
    return {config.output_keys[0]: out_path}


register_step(
    "compress",
    compress_step,
    compress_output_fn,
    optional=True,
    description="Compress video using H.264",
    config_class=CompressConfig,
    input_media_type="video",
)
