"""
Extrae y mejora audio de videos para transcripción.

Wrapper sobre enhance_audio.py — aplica el mismo pipeline a archivos de video
localizando los .mp4 del directorio actual.
"""

import argparse
import sys
from pathlib import Path

from clearvoice import ClearVoice
from enhance_audio import (
    file_key,
    load_cache,
    save_cache,
    extract_to_wav16k,
    normalize_lufs,
    to_m4a,
    MODEL,
)

VIDEO_EXTENSIONS = {".mp4", ".mkv", ".mov", ".avi"}


def process_video(src: Path, cv: ClearVoice, m4a: bool) -> Path | None:
    d = src.parent
    stem = src.stem

    tmp_raw  = d / f"{stem}._tmp_raw.wav"
    tmp_norm = d / f"{stem}._tmp_norm.wav"
    tmp_enh  = d / f"{stem}._tmp_enh.wav"
    out = d / f"{stem}_audio_enhanced.{'m4a' if m4a else 'wav'}"

    try:
        print("  [1/3] Extrayendo WAV 48kHz...")
        if not extract_to_wav16k(src, tmp_raw):
            raise RuntimeError("ffmpeg no pudo extraer el audio")

        print("  [2/3] Normalizando LUFS...")
        normalize_lufs(tmp_raw, tmp_norm)

        print(f"  [3/3] {MODEL}...")
        enhanced = cv(input_path=str(tmp_norm), online_write=False)
        cv.write(enhanced, output_path=str(tmp_enh))

        if m4a:
            if not to_m4a(tmp_enh, out):
                raise RuntimeError("ffmpeg no pudo convertir a M4A")
        else:
            tmp_enh.rename(out)
            tmp_enh = None

        mb = out.stat().st_size / (1024 * 1024)
        print(f"  -> {out.name} ({mb:.1f} MB)")
        return out

    except Exception as e:
        print(f"  ERROR: {e}")
        return None

    finally:
        for tmp in [tmp_raw, tmp_norm, tmp_enh]:
            if tmp is not None:
                tmp.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(
        description="Extrae y mejora audio de videos para transcripción",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  %(prog)s                   # todos los videos del directorio
  %(prog)s reunion.mp4       # un archivo
  %(prog)s *.mp4 --m4a       # salida en M4A
  %(prog)s reunion.mp4 --force
        """,
    )
    parser.add_argument(
        "files", nargs="*",
        help="Archivos a procesar (default: todos los videos del directorio)",
    )
    parser.add_argument(
        "--m4a", action="store_true",
        help="Guardar salida como M4A 192k en vez de WAV 48kHz",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Reprocesar aunque ya esté en caché",
    )
    args = parser.parse_args()

    work_dir = Path.cwd()
    cache = load_cache()

    if args.files:
        files = [
            Path(f) for f in args.files
            if Path(f).exists() and Path(f).suffix.lower() in VIDEO_EXTENSIONS
        ]
    else:
        files = sorted(
            f for f in work_dir.iterdir()
            if f.suffix.lower() in VIDEO_EXTENSIONS
            and "_enhanced" not in f.stem
            and not f.stem.startswith("._tmp_")
        )

    if not files:
        print(f"No se encontraron videos. Formatos: {', '.join(sorted(VIDEO_EXTENSIONS))}")
        sys.exit(0)

    pending = [f for f in files if args.force or file_key(f) not in cache]

    print(f"Encontrados:   {len(files)}")
    print(f"Ya en caché:   {len(files) - len(pending)}")
    print(f"Por procesar:  {len(pending)}")
    print(f"Modelo:        {MODEL}  |  Salida: {'M4A 192k' if args.m4a else 'WAV 48kHz'}")

    if not pending:
        print("\nTodo procesado. Usa --force para reprocesar.")
        sys.exit(0)

    print(f"\nCargando {MODEL}...")
    cv = ClearVoice(task="speech_enhancement", model_names=[MODEL])

    ok, failed = 0, []
    for i, f in enumerate(pending, 1):
        print(f"\n[{i}/{len(pending)}] {f.name}")
        result = process_video(f, cv, args.m4a)
        if result:
            cache[file_key(f)] = {"output": result.name}
            save_cache(cache)
            ok += 1
        else:
            failed.append(f.name)

    print(f"\n{'='*40}")
    print(f"Procesados: {ok}/{len(pending)}")
    if failed:
        print(f"Fallidos:   {', '.join(failed)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
