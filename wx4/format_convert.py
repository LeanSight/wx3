"""
Convert between different transcription data formats used by wx4 backends.
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


def wx3_chunks_to_aai_words(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Convert wx3 Whisper+alignment chunks to AssemblyAI word-level format.

    Input:  [{'text': ' hello world', 'timestamp': (1.5, 4.0), 'speaker': 'SPEAKER_00'}, ...]
    Output: [{'text': 'hello world', 'start': 1500, 'end': 4000,
              'confidence': 1.0, 'speaker': 'SPEAKER_00'}, ...]

    - text: leading space stripped (Whisper convention)
    - start/end: seconds converted to integer milliseconds
    - confidence: set to 1.0 (Whisper does not provide word-level confidence)
    """
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
