"""
Convert wx4 chunk lists to SRT subtitle format.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from common.grouping import group_chunks_by_sentences, group_chunks_by_speaker_only
from wx4.format_convert import assemblyai_words_to_chunks


def _format_timestamp(seconds: float) -> str:
    """Format seconds as SRT timestamp: HH:MM:SS,mmm"""
    total_ms = int(round(seconds * 1000))
    h = total_ms // 3_600_000
    total_ms %= 3_600_000
    m = total_ms // 60_000
    total_ms %= 60_000
    s = total_ms // 1_000
    ms = total_ms % 1_000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def chunks_to_srt(
    chunks: List[Dict[str, Any]],
    speaker_names: Optional[Dict[str, str]] = None,
) -> str:
    """
    Convert grouped chunks to SRT string.
    Each chunk becomes one SRT entry with optional [Speaker] prefix.
    """
    if not chunks:
        return ""

    lines = []
    for idx, chunk in enumerate(chunks, 1):
        text = chunk["text"]
        ts = chunk["timestamp"]
        speaker = chunk.get("speaker") or ""

        if speaker_names and speaker in speaker_names:
            speaker = speaker_names[speaker]

        start = _format_timestamp(ts[0])
        end = _format_timestamp(ts[1])

        if speaker:
            text = f"[{speaker}] {text}"

        lines.append(str(idx))
        lines.append(f"{start} --> {end}")
        lines.append(text)
        lines.append("")

    return "\n".join(lines)


def words_to_srt(
    words: List[Dict[str, Any]],
    speaker_names: Optional[Dict[str, str]] = None,
    output_file: Optional[str] = None,
    mode: str = "sentences",
) -> str:
    """
    Convert AssemblyAI word list to SRT string.

    mode: 'sentences' or 'speaker-only'
    Writes to output_file if given.
    """
    chunks = assemblyai_words_to_chunks(words)

    if mode == "sentences":
        grouped = group_chunks_by_sentences(chunks)
    elif mode == "speaker-only":
        grouped = group_chunks_by_speaker_only(chunks)
    else:
        raise ValueError(f"Invalid mode: {mode}. Use 'sentences' or 'speaker-only'")

    srt = chunks_to_srt(grouped, speaker_names)

    if output_file:
        Path(output_file).write_text(srt, encoding="utf-8")

    return srt
