"""
wx41 Pypyr Steps
"""
from pathlib import Path


def normalize(context):
    """Normalize step - just passes through."""
    audio_path = Path(context["audio_path"])
    context["normalized"] = str(audio_path)


def transcribe(context):
    """Transcribe step."""
    from wx41.transcribe_aai import transcribe_assemblyai
    from wx41.transcribe_whisper import transcribe_whisper

    audio_path = Path(context["normalized"])
    backend = context.get("backend", "assemblyai")
    api_key = context.get("api_key")

    if backend == "assemblyai":
        txt, jsn = transcribe_assemblyai(
            audio_path,
            api_key=api_key,
            lang=None,
            speakers=None,
            progress_callback=None,
        )
    elif backend == "whisper":
        txt, jsn = transcribe_whisper(
            audio_path,
            api_key=api_key,
            lang=None,
            speakers=None,
            progress_callback=None,
            model="openai/whisper-base",
        )
    else:
        raise RuntimeError(f"Backend {backend} not implemented yet")

    context["transcript_txt"] = str(txt)
    context["transcript_json"] = str(jsn)
