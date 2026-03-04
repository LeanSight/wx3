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
    mode: str = "sentences"
    max_chars: int = 50


def ms_to_seconds(ms: int) -> float:
    return ms / 1000.0


def format_timestamp(seconds: float) -> str:
    hours, rem = divmod(seconds, 3600)
    minutes, rem = divmod(rem, 60)
    secs, millis = divmod(rem, 1)
    return (
        f"{int(hours):02d}:{int(minutes):02d}:{int(secs):02d},{int(millis * 1000):03d}"
    )


def words_to_wx3_chunks(words: List[Dict]) -> List[Dict]:
    chunks = []
    for word in words:
        chunk = {
            "text": word["text"],
            "timestamp": (ms_to_seconds(word["start"]), ms_to_seconds(word["end"])),
            "speaker": word.get("speaker", "UNKNOWN"),
        }
        chunks.append(chunk)
    return chunks


def group_by_sentences(chunks: List[Dict], max_chars: int = 80) -> List[Dict]:
    if not chunks:
        return []

    groups = []
    current_group = []
    current_chars = 0
    current_start = chunks[0]["timestamp"][0]
    current_end = chunks[0]["timestamp"][1]

    for chunk in chunks:
        text = chunk["text"]
        if current_chars + len(text) > max_chars and current_group:
            groups.append(
                {
                    "text": " ".join(c["text"] for c in current_group),
                    "timestamp": (current_start, current_end),
                    "speaker": current_group[0].get("speaker", ""),
                }
            )
            current_group = []
            current_chars = 0
            current_start = chunk["timestamp"][0]

        current_group.append(chunk)
        current_chars += len(text) + 1
        current_end = chunk["timestamp"][1]

    if current_group:
        groups.append(
            {
                "text": " ".join(c["text"] for c in current_group),
                "timestamp": (current_start, current_end),
                "speaker": current_group[0].get("speaker", ""),
            }
        )

    return groups


def chunks_to_srt_lines(chunks: List[Dict]) -> List[str]:
    lines = []
    for i, chunk in enumerate(chunks, 1):
        start, end = chunk["timestamp"]
        text = chunk["text"]
        speaker = chunk.get("speaker", "")

        if speaker:
            formatted = f"[{speaker}] {text}"
        else:
            formatted = text

        lines.append(str(i))
        lines.append(f"{format_timestamp(start)} --> {format_timestamp(end)}")
        lines.append(formatted)
        lines.append("")

    return lines


def srt_step(ctx: PipelineContext, config: SRTConfig) -> PipelineContext:
    if not config.enabled:
        return ctx

    audio = ctx.src
    jsn_path = ctx.outputs.get("transcript_json")
    if not jsn_path or not jsn_path.exists():
        from wx41.steps import get_step_info

        t_info = get_step_info("transcribe")
        if t_info:
            jsn_path = predict_output_path(
                audio, "transcribe", t_info.config_class().output_keys[1]
            )

    if not jsn_path or not jsn_path.exists():
        raise RuntimeError(f"SRT step requires transcript_json output, but none found.")

    words = json.loads(jsn_path.read_text(encoding="utf-8"))

    wx3_chunks = words_to_wx3_chunks(words)

    if config.mode == "speaker":
        grouped = wx3_chunks
    else:
        grouped = group_by_sentences(wx3_chunks, max_chars=config.max_chars)

    lines = chunks_to_srt_lines(grouped)

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
    config_class=SRTConfig,
)
