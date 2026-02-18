"""
Limpia audio de reuniones en sala para transcripcion.

Pipeline:
    audio/video  ->  WAV 48kHz mono  ->  LUFS -23  ->  MossFormer2_SE_48K  ->  output
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from clearvoice import ClearVoice

MODEL = "MossFormer2_SE_48K"
TARGET_LUFS = -23.0
SUPPORTED = {".mp4", ".m4a", ".wav", ".mp3", ".flac", ".mkv", ".mov", ".avi"}
MEMORY_FILE = Path.cwd() / ".enhance_meeting_cache.json"


# ---------------------------------------------------------------------------
# Caché
# ---------------------------------------------------------------------------

def load_cache() -> dict:
    if MEMORY_FILE.exists():
        try:
            return json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def save_cache(cache: dict):
    MEMORY_FILE.write_text(
        json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def file_key(path: Path) -> str:
    s = path.stat()
    return f"{path.name}|{s.st_size}|{s.st_mtime}"


# ---------------------------------------------------------------------------
# Etapas del pipeline
# ---------------------------------------------------------------------------

def extract_to_wav(src: Path, dst: Path) -> bool:
    """Extrae/convierte a WAV 48 kHz mono."""
    result = subprocess.run(
        ["ffmpeg", "-y", "-i", str(src),
         "-vn", "-acodec", "pcm_s16le", "-ar", "48000", "-ac", "1",
         str(dst)],
        capture_output=True,
    )
    return result.returncode == 0


# Alias para compatibilidad con imports existentes
extract_to_wav16k = extract_to_wav


def measure_lufs(wav: Path) -> float:
    """Devuelve el loudness integrado en LUFS. -70 si silencio o error."""
    result = subprocess.run(
        ["ffmpeg", "-y", "-i", str(wav),
         "-af", "loudnorm=print_format=json", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    m = re.search(r'"input_i"\s*:\s*"([^"]+)"', result.stderr)
    if m and m.group(1) != "-inf":
        try:
            return float(m.group(1))
        except ValueError:
            pass
    return -70.0


def normalize_lufs(src: Path, dst: Path) -> bool:
    """Aplica ganancia para llevar el audio a TARGET_LUFS."""
    current = measure_lufs(src)
    if current <= -69.0:          # silencio — copiar sin tocar
        shutil.copy2(src, dst)
        return True

    gain_db = max(min(TARGET_LUFS - current, 30.0), -30.0)
    result = subprocess.run(
        ["ffmpeg", "-y", "-i", str(src),
         "-af", f"volume={gain_db:.2f}dB", str(dst)],
        capture_output=True,
    )
    if result.returncode != 0:
        shutil.copy2(src, dst)
    return True


def to_m4a(src: Path, dst: Path, bitrate: str = "192k") -> bool:
    """Comprime WAV a M4A AAC para almacenamiento."""
    result = subprocess.run(
        ["ffmpeg", "-y", "-i", str(src),
         "-acodec", "aac", "-b:a", bitrate, str(dst)],
        capture_output=True,
    )
    return result.returncode == 0


# ---------------------------------------------------------------------------
# Procesamiento de un archivo
# ---------------------------------------------------------------------------

def process(src: Path, cv: ClearVoice, m4a: bool) -> Path | None:
    d = src.parent
    stem = src.stem

    tmp_raw  = d / f"{stem}._tmp_raw.wav"
    tmp_norm = d / f"{stem}._tmp_norm.wav"
    tmp_enh  = d / f"{stem}._tmp_enh.wav"
    out = d / f"{stem}_enhanced.{'m4a' if m4a else 'wav'}"

    try:
        print("  [1/3] Extrayendo WAV 48kHz...")
        if not extract_to_wav(src, tmp_raw):
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


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Limpia audio de reuniones en sala para transcripción",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  %(prog)s                      # todos los archivos soportados del directorio
  %(prog)s reunion.mp4          # un archivo
  %(prog)s *.mp4 --m4a          # salida en M4A (para almacenamiento)
  %(prog)s reunion.mp4 --force  # reprocesar aunque esté en caché
        """,
    )
    parser.add_argument(
        "files", nargs="*",
        help="Archivos a procesar (default: todos los soportados en el directorio)",
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
            if Path(f).exists() and Path(f).suffix.lower() in SUPPORTED
        ]
    else:
        files = sorted(
            f for f in work_dir.iterdir()
            if f.suffix.lower() in SUPPORTED
            and "_enhanced" not in f.stem
            and not f.stem.startswith("._tmp_")
        )

    if not files:
        print(f"No se encontraron archivos. Formatos soportados: {', '.join(sorted(SUPPORTED))}")
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
        result = process(f, cv, args.m4a)
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
