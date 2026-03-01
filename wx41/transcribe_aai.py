import json
import os
import time
from pathlib import Path
from typing import Optional, Tuple, Callable
import assemblyai as aai

def transcribe_assemblyai(
    audio: Path,
    api_key: Optional[str] = None,
    lang: Optional[str] = None,
    speakers: Optional[int] = None,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> Tuple[Path, Path]:
    key = api_key or os.environ.get('ASSEMBLY_AI_KEY')
    if not key:
        raise RuntimeError('AssemblyAI API key not set')
    aai.settings.api_key = key

    config = aai.TranscriptionConfig(
        speech_model=aai.SpeechModel.best,
        speaker_labels=True,
        speakers_expected=speakers,
        language_code=lang,
        language_detection=(lang is None),
    )

    transcript = aai.Transcriber(config=config).submit(str(audio))
    if progress_callback: progress_callback(0, 3)

    while transcript.status in {aai.TranscriptStatus.queued, aai.TranscriptStatus.processing}:
        time.sleep(3)
        transcript = transcript.wait_for_completion()
        if progress_callback and transcript.status == aai.TranscriptStatus.processing:
            progress_callback(1, 3)

    if transcript.status == aai.TranscriptStatus.error:
        raise RuntimeError(f'AssemblyAI error: {transcript.error}')

    if progress_callback: progress_callback(3, 3)

    words = [{'text': w.text, 'start': w.start, 'end': w.end, 'confidence': w.confidence, 'speaker': w.speaker} for w in transcript.words]
    json_path = audio.parent / f'{audio.stem}_timestamps.json'
    json_path.write_text(json.dumps(words, ensure_ascii=False, indent=2), encoding='utf-8')

    lines = []
    for utt in transcript.utterances:
        s = utt.start // 1000
        h, rem = divmod(s, 3600)
        m, sec = divmod(rem, 60)
        ts = f'{h:02d}:{m:02d}:{sec:02d}' if h else f'{m:02d}:{sec:02d}'
        lines.append(f'[{ts}] Speaker {utt.speaker}: {utt.text}')

    txt_path = audio.parent / f'{audio.stem}_transcript.txt'
    txt_path.write_text('\n'.join(lines), encoding='utf-8')

    return txt_path, json_path
