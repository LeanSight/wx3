"""
Group transcription chunks into natural segments.
Extracted from wx3/sentence_grouping.py with ASCII-only strings.
"""

import re
from typing import Any, Dict, List, Optional


def is_sentence_end(text: str) -> bool:
    """Returns True if text ends with a sentence delimiter (. ! ? ;)."""
    text = text.rstrip()
    return bool(re.search(r'[.!?;]["\'\)]*$', text))


def is_strong_pause(text: str) -> bool:
    """Returns True if text ends with a strong pause marker (, or :)."""
    text = text.rstrip()
    return bool(re.search(r'[,:]["\'\)]*$', text))


def group_chunks_by_sentences(
    chunks: List[Dict[str, Any]],
    max_chars: int = 80,
    max_duration_s: float = 10.0,
) -> List[Dict[str, Any]]:
    """
    Group chunks into segments based on complete sentences.

    Priority order:
    1. Speaker change -> always new segment
    2. Sentence end (. ! ? ;)
    3. Strong pause (, :) when limits exceeded
    4. Absolute limits (1.5x max_chars or max_duration_s)
    """
    if not chunks:
        return []

    segments: List[Dict[str, Any]] = []
    current = _empty(chunks[0].get("speaker"))

    for chunk in chunks:
        info = _extract(chunk)
        if info is None:
            continue
        text, start, end, speaker = info

        # Priority 1: speaker change
        if speaker and speaker != current["speaker"]:
            if current["chunks"]:
                _finalize(current, segments)
            current = _empty(speaker)
            current["chunks"] = [chunk]
            current["start"] = start
            current["end"] = end
            continue

        temp_text, duration = _metrics(current, chunk, end)

        # Priority 2: sentence end
        if is_sentence_end(text):
            if not current["chunks"]:
                current["start"] = start
            current["chunks"].append(chunk)
            current["end"] = end
            _finalize(current, segments)
            current = _empty(speaker)
            continue

        # Priority 3: strong pause + limits exceeded
        if current["chunks"] and (
            len(temp_text) > max_chars or duration > max_duration_s
        ):
            if is_strong_pause(current["chunks"][-1]["text"].strip()):
                _finalize(current, segments)
                current = _empty(speaker)
                current["chunks"] = [chunk]
                current["start"] = start
                current["end"] = end
                continue

        # Priority 4: absolute limits
        if len(temp_text) > max_chars * 1.5 or duration > max_duration_s * 1.5:
            if current["chunks"]:
                _finalize(current, segments)
            current = _empty(speaker)
            current["chunks"] = [chunk]
            current["start"] = start
            current["end"] = end
            continue

        if not current["chunks"]:
            current["start"] = start
        current["chunks"].append(chunk)
        current["end"] = end

    if current["chunks"]:
        _finalize(current, segments)

    return segments


def group_chunks_by_speaker_only(
    chunks: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Group chunks, splitting only when the speaker changes."""
    if not chunks:
        return []

    segments: List[Dict[str, Any]] = []
    current = _empty(chunks[0].get("speaker"))

    for chunk in chunks:
        info = _extract(chunk)
        if info is None:
            continue
        text, start, end, speaker = info

        if speaker and speaker != current["speaker"]:
            if current["chunks"]:
                _finalize(current, segments)
            current = _empty(speaker)
            current["chunks"] = [chunk]
            current["start"] = start
            current["end"] = end
        else:
            if not current["chunks"]:
                current["start"] = start
            current["chunks"].append(chunk)
            current["end"] = end

    if current["chunks"]:
        _finalize(current, segments)

    return segments


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _empty(speaker: Optional[str] = None) -> Dict[str, Any]:
    return {"chunks": [], "speaker": speaker, "start": None, "end": None}


def _extract(chunk: Dict[str, Any]) -> Optional[tuple]:
    text = chunk["text"].strip()
    if not text:
        return None
    ts = chunk.get("timestamp", (None, None))
    if isinstance(ts, list):
        ts = tuple(ts)
    if not isinstance(ts, tuple) or len(ts) != 2:
        return None
    start, end = ts
    if start is None or end is None:
        return None
    return (text, start, end, chunk.get("speaker"))


def _metrics(current: Dict[str, Any], chunk: Dict[str, Any], end: float) -> tuple:
    temp = " ".join(c["text"].strip() for c in current["chunks"] + [chunk])
    duration = (end - current["start"]) if current["start"] is not None else 0
    return (temp, duration)


def _finalize(current: Dict[str, Any], segments: List[Dict[str, Any]]) -> None:
    text = " ".join(c["text"].strip() for c in current["chunks"])
    segments.append(
        {
            "text": text,
            "timestamp": (current["start"], current["end"]),
            "speaker": current["speaker"],
        }
    )
