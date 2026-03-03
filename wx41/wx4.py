import dataclasses
from pathlib import Path
from typing import List, Optional, Dict, Any
from functools import partial

from wx41.context import PipelineConfig, PipelineContext, StepConfig
from wx41.pipeline_engine import Pipeline, NamedStep, PipelineObserver, PipelineObserver
from wx41.steps import get_all_steps


class MediaType:
    AUDIO = "audio"
    VIDEO = "video"


def detect_media_type(src: Path) -> str:
    video_exts = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v"}
    if src.suffix.lower() in video_exts:
        return MediaType.VIDEO
    return MediaType.AUDIO


def _instantiate_step(
    step_name: str, config: PipelineConfig, all_steps: Dict[str, Any]
) -> Optional[NamedStep]:
    step_info = all_steps.get(step_name)
    if not step_info:
        return None

    # Get config from settings or use default
    step_config = config.settings.get(step_name)
    if not step_config:
        if step_info.config_class:
            step_config = step_info.config_class()
        else:
            return None  # Should not happen with current registry

    # Skip if explicitly disabled
    if isinstance(step_config, StepConfig) and not step_config.enabled:
        return None

    step_fn = partial(step_info.step_fn, config=step_config)
    output_fn = None
    if step_info.output_fn:
        output_fn = partial(step_info.output_fn, config=step_config)

    return NamedStep(name=step_name, fn=step_fn, output_fn=output_fn)


def build_audio_pipeline(
    config: PipelineConfig, observers: List[PipelineObserver]
) -> Pipeline:
    all_steps = get_all_steps()
    # Explicit order for Audio
    sequence = ["normalize", "enhance", "transcribe", "srt", "black_video"]

    steps = []
    for name in sequence:
        if name in config.settings:
            step = _instantiate_step(name, config, all_steps)
            if step:
                steps.append(step)

    return Pipeline(steps, observers)


def build_video_pipeline(
    config: PipelineConfig, observers: List[PipelineObserver]
) -> Pipeline:
    all_steps = get_all_steps()
    # Explicit order for Video
    # Per user: normalize -> enhance -> transcribe -> srt -> compress
    sequence = ["normalize", "enhance", "transcribe", "srt", "compress"]

    steps = []
    for name in sequence:
        if name in config.settings:
            step = _instantiate_step(name, config, all_steps)
            if step:
                steps.append(step)

    return Pipeline(steps, observers)


class MediaOrchestrator:
    def __init__(self, config: PipelineConfig, observers: List[PipelineObserver]):
        self._config = config
        self._observers = observers

    def run(self, src: Path, dry_run: bool = False) -> PipelineContext:
        media_type = detect_media_type(src)
        ctx = PipelineContext(
            src=src, media_type=media_type, force=self._config.force, dry_run=dry_run
        )

        if media_type == MediaType.VIDEO:
            pipeline = build_video_pipeline(self._config, self._observers)
        else:
            pipeline = build_audio_pipeline(self._config, self._observers)

        try:
            return pipeline.run(ctx, dry_run=dry_run)
        except KeyboardInterrupt:
            return dataclasses.replace(ctx, interrupted=True)
