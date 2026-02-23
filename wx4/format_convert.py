"""
Convert AssemblyAI word-level data to wx4 chunk format.
"""

from typing import Any, Dict, List


def ms_to_seconds(ms: int) -> float:
    """Convert milliseconds to seconds."""
    return ms / 1000.0


def assemblyai_words_to_chunks(words: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Convert AssemblyAI word list to wx4 chunk list.

    Input:  [{'text': 'word', 'start': 0, 'end': 500, 'speaker': 'A'}, ...]
    Output: [{'text': 'word', 'timestamp': (0.0, 0.5), 'speaker': 'A'}, ...]
    """
    return [
        {
            "text": w["text"],
            "timestamp": (ms_to_seconds(w["start"]), ms_to_seconds(w["end"])),
            "speaker": w.get("speaker", "UNKNOWN"),
        }
        for w in words
    ]
