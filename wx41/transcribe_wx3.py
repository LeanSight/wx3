import json
from pathlib import Path
from typing import Optional, Tuple

from wx41.format_convert import wx3_chunks_to_aai_words


def transcribe_with_whisper(
    audio: Path,
    lang: Optional[str] = None,
    speakers: Optional[int] = None,
    hf_token: Optional[str] = None,
    device: str = "auto",
    whisper_model: Optional[str] = None,
) -> Tuple[Path, Path]:
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

    if whisper_model is None:
        whisper_model = "openai/whisper-large-v3"

    device_str = None if device == "auto" else device

    audio_data = load_media(audio)

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

    trans_pipeline = create_transcription_pipeline(
        model=whisper_model,
        device=device_str,
    )
    trans_result = perform_transcription(
        audio=audio_data,
        pipeline=trans_pipeline,
        language=lang,
    )

    chunks = align_diarization_with_transcription(diar_segments, trans_result.chunks)
    words = wx3_chunks_to_aai_words(chunks)

    json_path = audio.parent / f"{audio.stem}_timestamps.json"
    tmp_path = json_path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(words, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.rename(json_path)

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
