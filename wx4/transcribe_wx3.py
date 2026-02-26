"""
Transcribe audio via local Whisper + PyAnnote diarization (wx3 backend).

wx3 modules (alignment, diarization, input_media, transcription) are imported
at module level so they can be patched cleanly in tests. They are available
because wx4 runs from the wx3 project root which is on sys.path.
"""

import json
from pathlib import Path
from typing import Optional, Tuple

from alignment import align_diarization_with_transcription
from diarization import (
    create_pipeline as create_diarization_pipeline,
    format_diarization_result,
    perform_diarization,
)
from input_media import load_media
from transcription import (
    create_pipeline as create_transcription_pipeline,
    perform_transcription,
)
from wx4.format_convert import wx3_chunks_to_aai_words


def transcribe_with_whisper(
    audio: Path,
    lang: Optional[str] = None,
    speakers: Optional[int] = None,
    hf_token: Optional[str] = None,
    device: str = "auto",
    whisper_model: Optional[str] = None,
) -> Tuple[Path, Path]:
    """
    Transcribe audio using Whisper + PyAnnote, saving output in AssemblyAI word format.

    Parameters
    ----------
    audio : Path
        Input audio/video file.
    lang : str, optional
        Language code (e.g. 'es', 'en'). None = auto-detect.
    speakers : int, optional
        Expected number of speakers for diarization. None = auto-detect.
    hf_token : str, optional
        HuggingFace token for PyAnnote diarization. If None, diarization is
        skipped and all output is attributed to a single unnamed speaker.
    device : str
        Compute device: 'auto', 'cpu', 'cuda', or 'mps'.
    whisper_model : str, optional
        Whisper model identifier. Default: 'openai/whisper-large-v3'.

    Returns
    -------
    (txt_path, json_path)
        txt_path  : human-readable transcript  ({stem}_transcript.txt)
        json_path : word-level JSON in AssemblyAI format ({stem}_timestamps.json)

    Raises
    ------
    RuntimeError
        If transcription fails.
    """
    if whisper_model is None:
        whisper_model = "openai/whisper-large-v3"

    device_str = None if device == "auto" else device

    # --- 1. Load audio ---
    audio_data = load_media(audio)

    # --- 2. Diarization (optional, requires hf_token) ---
    diar_segments = []
    if hf_token:
        diar_pipeline = create_diarization_pipeline(token=hf_token, device=device_str)
        diar_result, _ = perform_diarization(
            audio_path=audio,
            pipeline=diar_pipeline,
            num_speakers=speakers,
            device=device_str,
        )
        diar_dict = format_diarization_result(diar_result)
        diar_segments = diar_dict.get("speakers", [])

    # --- 3. Transcription ---
    trans_pipeline = create_transcription_pipeline(
        model=whisper_model,
        device=device_str,
    )
    trans_result = perform_transcription(
        audio=audio_data,
        pipeline=trans_pipeline,
        language=lang,
    )

    # --- 4. Align transcription with diarization ---
    chunks = align_diarization_with_transcription(diar_segments, trans_result.chunks)

    # --- 5. Convert to AssemblyAI word-level format ---
    words = wx3_chunks_to_aai_words(chunks)

    # --- 6. Write JSON (atomic: tmp -> rename) ---
    json_path = audio.parent / f"{audio.stem}_timestamps.json"
    tmp_path = json_path.with_suffix(".json.tmp")
    tmp_path.write_text(
        json.dumps(words, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    tmp_path.rename(json_path)

    # --- 7. Write human-readable TXT ---
    lines = []
    prev_speaker = None
    for w in words:
        speaker = w.get("speaker", "")
        start_ms = w["start"]
        s = start_ms // 1000
        h, rem = divmod(s, 3600)
        m, sec = divmod(rem, 60)
        ts = f"{h:02d}:{m:02d}:{sec:02d}" if h else f"{m:02d}:{sec:02d}"
        if speaker != prev_speaker:
            lines.append(f"[{ts}] {speaker}: {w['text']}")
            prev_speaker = speaker
        else:
            lines.append(f"  {w['text']}")

    txt_path = audio.parent / f"{audio.stem}_transcript.txt"
    txt_path.write_text("\n".join(lines), encoding="utf-8")

    return txt_path, json_path
