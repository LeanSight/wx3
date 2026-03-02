import json
import dataclasses
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, List

from wx41.context import PipelineContext
from wx41.steps import register_step, predict_output_path


@dataclass(frozen=True)
class SRTConfig:
    enabled: bool = True
    output_keys: tuple = ("srt",)


def format_timestamp(seconds: float) -> str:
    td = float(seconds)
    hours, rem = divmod(td, 3600)
    minutes, rem = divmod(rem, 60)
    secs, millis = divmod(rem, 1)
    return f"{int(hours):02d}:{int(minutes):02d}:{int(secs):02d},{int(millis*1000):03d}"


def srt_step(ctx: PipelineContext, config: SRTConfig) -> PipelineContext:
    if not config.enabled:
        return ctx
        
    audio = ctx.src
    jsn_path = ctx.outputs.get("transcript_json")
    if not jsn_path or not jsn_path.exists():
        # Fallback to predicting if not in outputs but might be on disk
        # (though pipeline should have it in outputs if it ran)
        from wx41.steps import get_step_info
        t_info = get_step_info("transcribe")
        if t_info:
            jsn_path = predict_output_path(audio, "transcribe", t_info.config_class().output_keys[1])

    if not jsn_path or not jsn_path.exists():
        raise RuntimeError(f"SRT step requires transcript_json output, but none found.")

    words = json.loads(jsn_path.read_text(encoding="utf-8"))
    
    lines = []
    for i, word in enumerate(words, 1):
        start = format_timestamp(word["start"])
        end = format_timestamp(word["end"])
        text = word["text"]
        lines.append(f"{i}")
        lines.append(f"{start} --> {end}")
        lines.append(f"{text}\n")

    out_path = predict_output_path(audio, "srt", config.output_keys[0])
    out_path.write_text("\n".join(lines), encoding="utf-8")
    
    new_outputs = {**ctx.outputs, config.output_keys[0]: out_path}
    return dataclasses.replace(ctx, outputs=new_outputs)


def srt_output_fn(ctx: PipelineContext, config: SRTConfig) -> Dict[str, Path]:
    if not config.enabled:
        return {}
    out_path = predict_output_path(ctx.src, "srt", config.output_keys[0])
    return {config.output_keys[0]: out_path}


register_step(
    "srt",
    srt_step,
    srt_output_fn,
    optional=True,
    description="Generate SRT subtitles from transcription JSON",
    config_class=SRTConfig
)
