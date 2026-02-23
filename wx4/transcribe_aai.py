"""
Transcribe audio via AssemblyAI with speaker diarization.
"""

import json
import os
from pathlib import Path
from typing import Optional, Tuple

import assemblyai as aai


def transcribe_assemblyai(
    audio: Path,
    lang: Optional[str] = None,
    speakers: Optional[int] = None,
) -> Tuple[Path, Path]:
    """
    Transcribe audio with AssemblyAI (best model + speaker labels).

    Returns (txt_path, json_path).
    Raises RuntimeError if ASSEMBLY_AI_KEY is not set or transcript fails.
    """
    api_key = os.environ.get("ASSEMBLY_AI_KEY")
    if not api_key:
        raise RuntimeError("ASSEMBLY_AI_KEY env var not set")

    aai.settings.api_key = api_key

    config = aai.TranscriptionConfig(
        speech_model=aai.SpeechModel.best,
        speaker_labels=True,
        speakers_expected=speakers,
        language_code=lang,
        language_detection=(lang is None),
    )

    transcript = aai.Transcriber(config=config).transcribe(str(audio))

    if transcript.status == aai.TranscriptStatus.error:
        raise RuntimeError(f"AssemblyAI error: {transcript.error}")

    # Word-level JSON
    words = [
        {
            "text": w.text,
            "start": w.start,
            "end": w.end,
            "confidence": w.confidence,
            "speaker": w.speaker,
        }
        for w in transcript.words
    ]
    json_path = audio.parent / f"{audio.stem}_timestamps.json"
    json_path.write_text(
        json.dumps(words, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Human-readable TXT
    lines = []
    for utt in transcript.utterances:
        ms = utt.start
        s = ms // 1000
        h, rem = divmod(s, 3600)
        m, sec = divmod(rem, 60)
        ts = f"{h:02d}:{m:02d}:{sec:02d}" if h else f"{m:02d}:{sec:02d}"
        lines.append(f"[{ts}] Speaker {utt.speaker}: {utt.text}")

    txt_path = audio.parent / f"{audio.stem}_transcript.txt"
    txt_path.write_text("\n".join(lines), encoding="utf-8")

    return txt_path, json_path
