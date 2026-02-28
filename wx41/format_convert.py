from typing import Any, Dict, List


def ms_to_seconds(ms: int) -> float:
    return ms / 1000.0


def assemblyai_words_to_chunks(words: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {
            "text": w["text"],
            "timestamp": (ms_to_seconds(w["start"]), ms_to_seconds(w["end"])),
            "speaker": w.get("speaker", "UNKNOWN"),
        }
        for w in words
    ]


def wx3_chunks_to_aai_words(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {
            "text": c["text"].lstrip(" "),
            "start": int(c["timestamp"][0] * 1000),
            "end": int(c["timestamp"][1] * 1000),
            "confidence": 1.0,
            "speaker": c.get("speaker", "UNKNOWN"),
        }
        for c in chunks
    ]
