"""
Pipeline completo: enhance -> transcribe -> SRT [-> video]

Para cada archivo de entrada:
  1. [enhance]    enhance_audio.process()  o  enhance_video_audio.process_video()
  2. [transcribe] assembly_transcribe.transcribe_file()
  3. [to_srt]     assemblyai_json_to_srt.words_to_srt()
  4. [video]      (opcional, --videooutput)
                  audio -> MP4 con video negro  (convert_audio_to_mp4)
                  video -> MP4 con audio mejorado reemplazado  (ffmpeg stream copy)

Estructura de salida para reunion.mp4 con --videooutput:
    reunion_audio_enhanced.m4a
    reunion_audio_enhanced_transcript.txt
    reunion_audio_enhanced_timestamps.json
    reunion_audio_enhanced_timestamps.srt
    reunion_audio_enhanced_video.mp4      <- video original + audio mejorado

Estructura de salida para reunion.mp3 con --videooutput:
    reunion_enhanced.m4a
    reunion_enhanced_transcript.txt
    reunion_enhanced_timestamps.json
    reunion_enhanced_timestamps.srt
    reunion_enhanced_video.mp4            <- video negro + audio mejorado
"""

import argparse
import json
import os
import sys
from pathlib import Path

import ffmpeg
from constants import VIDEO_EXTENSIONS
from assemblyai_json_to_srt import words_to_srt
from assembly_transcribe import transcribe_file
from enhance_audio import load_cache, save_cache, file_key, MODEL
from convert_audio_to_mp4 import convert as audio_to_black_video

import assemblyai as aai


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_speakers_map(raw: str | None) -> dict[str, str] | None:
    """Parsea 'A=Marcel,B=Agustin' -> {'A': 'Marcel', 'B': 'Agustin'}."""
    if not raw:
        return None
    result = {}
    for pair in raw.split(","):
        pair = pair.strip()
        if "=" in pair:
            k, v = pair.split("=", 1)
            result[k.strip()] = v.strip()
    return result or None


def is_video(path: Path) -> bool:
    return path.suffix.lower() in set(VIDEO_EXTENSIONS)


def make_video_output(src: Path, enhanced_path: Path) -> Path | None:
    """
    Genera el MP4 de salida con el audio mejorado.
      - Audio input: video negro + audio mejorado (convert_audio_to_mp4)
      - Video input: video original + audio mejorado (stream copy, sin recodificar)
    Devuelve la ruta del MP4 generado, o None si falla.
    """
    out = enhanced_path.parent / f"{enhanced_path.stem}_video.mp4"

    if is_video(src):
        # Reemplazar pista de audio: copiar video + nuevo audio, sin recodificar
        try:
            (
                ffmpeg.output(
                    ffmpeg.input(str(src)).video,
                    ffmpeg.input(str(enhanced_path)).audio,
                    str(out),
                    vcodec="copy",
                    acodec="copy",
                    movflags="+faststart",
                    shortest=None,
                )
                .run(overwrite_output=True, capture_stdout=True, capture_stderr=True)
            )
            return out
        except ffmpeg.Error as e:
            print(f"  ERROR video merge: {e.stderr.decode(errors='replace')[-400:]}")
            return None
    else:
        # Audio: generar video negro con audio mejorado
        ok = audio_to_black_video(enhanced_path, out)
        return out if ok else None


# ---------------------------------------------------------------------------
# Pipeline por archivo
# ---------------------------------------------------------------------------

def process_file(
    src: Path,
    cv,                          # ClearVoice | None si --skip-enhance
    m4a: bool,
    language: str | None,
    speakers: int | None,
    srt_mode: str,
    speaker_names: dict[str, str] | None,
    skip_enhance: bool,
    force: bool,
    cache: dict,
    videooutput: bool = False,
) -> bool:
    print(f"\n{'-'*50}")
    print(f"Archivo: {src.name}")

    # ------------------------------------------------------------------
    # Paso 1: enhance
    # ------------------------------------------------------------------
    if skip_enhance:
        enhanced_path = src
        print("  [enhance] Saltado (--skip-enhance)")
    else:
        key = file_key(src)
        cached = cache.get(key)
        if cached and not force:
            enhanced_path = src.parent / cached["output"]
            if enhanced_path.exists():
                print(f"  [enhance] Cache -> {enhanced_path.name}")
            else:
                cached = None  # archivo borrado, reprocesar

        if not cached or force:
            if is_video(src):
                from enhance_video_audio import process_video
                enhanced_path = process_video(src, cv, m4a)
            else:
                from enhance_audio import process
                enhanced_path = process(src, cv, m4a)

            if enhanced_path is None:
                print(f"  ERROR: enhance fallo para {src.name}")
                return False

            cache[file_key(src)] = {"output": enhanced_path.name}
            save_cache(cache)

    # ------------------------------------------------------------------
    # Paso 2: transcribe
    # ------------------------------------------------------------------
    print(f"  [transcribe] {enhanced_path.name} -> TXT + JSON")
    try:
        txt_path, json_path = transcribe_file(enhanced_path, language, speakers)
    except RuntimeError as e:
        print(f"  ERROR: {e}")
        return False

    print(f"    TXT:  {txt_path.name}")
    print(f"    JSON: {json_path.name}")

    # ------------------------------------------------------------------
    # Paso 3: SRT
    # ------------------------------------------------------------------
    words = json.loads(json_path.read_text(encoding="utf-8"))
    srt_path = json_path.with_suffix(".srt")
    words_to_srt(
        words=words,
        speaker_names=speaker_names,
        output_file=str(srt_path),
        mode=srt_mode,
    )
    print(f"    SRT:  {srt_path.name}")

    # ------------------------------------------------------------------
    # Paso 4: video output (opcional)
    # ------------------------------------------------------------------
    if videooutput:
        print(f"  [video] generando MP4...")
        video_path = make_video_output(src, enhanced_path)
        if video_path:
            mb = video_path.stat().st_size / (1024 * 1024)
            print(f"    MP4:  {video_path.name} ({mb:.1f} MB)")
        else:
            print("    ERROR: no se pudo generar el video")

    return True


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Pipeline enhance -> transcribe -> SRT para reuniones grabadas",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  %(prog)s reunion.mp4 -l es --type speaker
  %(prog)s reunion_enhanced.wav -l es --skip-enhance
  %(prog)s *.mp4 -l es --speakers-map "A=Marcel,B=Agustin"
        """,
    )
    parser.add_argument(
        "files", nargs="*",
        help="Archivos a procesar (default: todos los soportados en el directorio)",
    )
    parser.add_argument(
        "-l", "--language",
        default=None,
        help="Codigo de idioma (ej: es, en). Default: deteccion automatica",
    )
    parser.add_argument(
        "-s", "--speakers",
        type=int,
        default=None,
        help="Numero esperado de hablantes. Default: deteccion automatica",
    )
    parser.add_argument(
        "--type",
        dest="srt_type",
        choices=["sub", "speaker"],
        default="speaker",
        help="Modo SRT: 'sub' = agrupado por oraciones, 'speaker' = por hablante (default: speaker)",
    )
    parser.add_argument(
        "--speakers-map",
        default=None,
        metavar="A=Nombre,B=Nombre",
        help="Mapeo de IDs de hablante a nombres (ej: 'A=Marcel,B=Agustin')",
    )
    parser.add_argument(
        "--skip-enhance",
        action="store_true",
        help="Saltar el paso de enhancement (para archivos ya mejorados)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Reprocesar aunque el enhance este en cache",
    )
    parser.add_argument(
        "--wav",
        action="store_true",
        help="Guardar audio mejorado como WAV 48kHz en lugar de M4A AAC (default)",
    )
    parser.add_argument(
        "--videooutput",
        action="store_true",
        help=(
            "Generar MP4 de salida: "
            "audio -> video negro + audio mejorado, "
            "video -> video original + audio mejorado"
        ),
    )
    args = parser.parse_args()

    # API key AssemblyAI
    api_key = os.environ.get("ASSEMBLY_AI_KEY")
    if not api_key:
        print("Error: variable de entorno ASSEMBLY_AI_KEY no definida", file=sys.stderr)
        sys.exit(1)
    aai.settings.api_key = api_key

    # Mapeo de hablantes
    speaker_names = parse_speakers_map(args.speakers_map)

    # Modo SRT
    srt_mode = "speaker-only" if args.srt_type == "speaker" else "sentences"

    # Archivos a procesar
    from enhance_audio import SUPPORTED as AUDIO_SUPPORTED
    ALL_SUPPORTED = AUDIO_SUPPORTED | set(ext.lower() for ext in VIDEO_EXTENSIONS)

    work_dir = Path.cwd()
    if args.files:
        files = [
            Path(f) for f in args.files
            if Path(f).exists() and Path(f).suffix.lower() in ALL_SUPPORTED
        ]
    else:
        files = sorted(
            f for f in work_dir.iterdir()
            if f.suffix.lower() in ALL_SUPPORTED
            and "_enhanced" not in f.stem
            and not f.stem.startswith("._tmp_")
        )

    if not files:
        print(f"No se encontraron archivos soportados: {', '.join(sorted(ALL_SUPPORTED))}")
        sys.exit(0)

    print(f"Archivos:  {len(files)}")
    print(f"Idioma:    {args.language or 'auto'}")
    print(f"Hablantes: {args.speakers or 'auto'}")
    print(f"Modo SRT:  {srt_mode}")
    if speaker_names:
        print(f"Nombres:   {speaker_names}")

    # Cargar ClearVoice solo si se necesita
    cv = None
    if not args.skip_enhance:
        print(f"\nCargando {MODEL}...")
        from clearvoice import ClearVoice
        cv = ClearVoice(task="speech_enhancement", model_names=[MODEL])

    cache = load_cache()
    ok, failed = 0, []

    for src in files:
        success = process_file(
            src=src,
            cv=cv,
            m4a=not args.wav,
            language=args.language,
            speakers=args.speakers,
            srt_mode=srt_mode,
            speaker_names=speaker_names,
            skip_enhance=args.skip_enhance,
            force=args.force,
            cache=cache,
            videooutput=args.videooutput,
        )
        if success:
            ok += 1
        else:
            failed.append(src.name)

    print(f"\n{'='*50}")
    print(f"Completados: {ok}/{len(files)}")
    if failed:
        print(f"Fallidos:    {', '.join(failed)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
