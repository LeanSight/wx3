"""
Transcribe audio con AssemblyAI usando el mejor modelo disponible
con detección de hablantes.

Pipeline:
    audio (WAV/M4A/MP3)  →  AssemblyAI (best + speaker_labels)  →  TXT + JSON
"""

import argparse
import json
import os
import sys
from pathlib import Path

import assemblyai as aai


def ms_to_timestamp(ms: int) -> str:
    """Convierte milisegundos a HH:MM:SS."""
    s = ms // 1000
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h:
        return f"{h:02d}:{m:02d}:{sec:02d}"
    return f"{m:02d}:{sec:02d}"


def transcribe_file(
    audio_path: Path,
    language: str | None,
    speakers: int | None,
) -> tuple[Path, Path]:
    """
    Transcribe y guarda TXT + JSON de timestamps.

    Guarda:
        <stem>_transcript.txt  — formato legible por hablante
        <stem>_timestamps.json — word-level data con speaker

    Devuelve (txt_path, json_path).
    """
    config = aai.TranscriptionConfig(
        speech_model=aai.SpeechModel.best,
        speaker_labels=True,
        speakers_expected=speakers,
        language_code=language,
        language_detection=language is None,
    )

    print(f"Subiendo {audio_path.name}...")
    transcript = aai.Transcriber(config=config).transcribe(str(audio_path))

    if transcript.status == aai.TranscriptStatus.error:
        raise RuntimeError(f"AssemblyAI error: {transcript.error}")

    # JSON de timestamps (word-level)
    words = [
        {"text": w.text, "start": w.start, "end": w.end,
         "confidence": w.confidence, "speaker": w.speaker}
        for w in transcript.words
    ]
    json_path = audio_path.parent / f"{audio_path.stem}_timestamps.json"
    json_path.write_text(json.dumps(words, ensure_ascii=False, indent=2), encoding="utf-8")

    # TXT legible
    lines = []
    for utt in transcript.utterances:
        ts = ms_to_timestamp(utt.start)
        lines.append(f"[{ts}] Speaker {utt.speaker}: {utt.text}")
    txt_path = audio_path.parent / f"{audio_path.stem}_transcript.txt"
    txt_path.write_text("\n".join(lines), encoding="utf-8")

    return txt_path, json_path


def main():
    parser = argparse.ArgumentParser(
        description="Transcribe audio con detección de hablantes via AssemblyAI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  %(prog)s reunion_enhanced.wav
  %(prog)s reunion_enhanced.wav -l es
  %(prog)s reunion_enhanced.wav -l es -s 3
  %(prog)s reunion_enhanced.wav -o transcripcion.txt
        """,
    )
    parser.add_argument(
        "audio",
        help="Archivo de audio a transcribir (WAV, MP3, M4A, etc.)",
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="Archivo de salida TXT (default: <audio>_transcript.txt)",
    )
    parser.add_argument(
        "-l", "--language",
        default=None,
        help="Código de idioma (ej: es, en, pt). Default: detección automática",
    )
    parser.add_argument(
        "-s", "--speakers",
        type=int,
        default=None,
        help="Número esperado de hablantes. Default: detección automática",
    )
    args = parser.parse_args()

    # API key
    api_key = os.environ.get("ASSEMBLY_AI_KEY")
    if not api_key:
        print("Error: variable de entorno ASSEMBLY_AI_KEY no definida", file=sys.stderr)
        sys.exit(1)
    aai.settings.api_key = api_key

    audio_path = Path(args.audio)
    if not audio_path.exists():
        print(f"Error: no se encontró el archivo {audio_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Modelo:    best  |  Idioma: {args.language or 'auto'}  |  Hablantes: {args.speakers or 'auto'}")

    try:
        txt_path, json_path = transcribe_file(audio_path, args.language, args.speakers)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Respetar -o si se especificó (mover el TXT al destino pedido)
    if args.output:
        out_path = Path(args.output)
        txt_path.rename(out_path)
        txt_path = out_path

    lines = txt_path.read_text(encoding="utf-8").count("\n") + 1
    print(f"Guardado:  {txt_path}  ({lines} turnos de habla)")
    print(f"Timestamps: {json_path}")


if __name__ == "__main__":
    main()
