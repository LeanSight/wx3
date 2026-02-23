"""
Limpia audio de reuniones en sala para transcripcion.

Pipeline:
    audio/video  ->  WAV 48kHz mono  ->  LUFS -23  ->  MossFormer2_SE_48K  ->  AAC M4A
"""

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

import ffmpeg
import torch
from clearvoice import ClearVoice

MODEL = "MossFormer2_SE_48K"
TARGET_LUFS = -23.0
SUPPORTED = {".mp4", ".m4a", ".wav", ".mp3", ".flac", ".mkv", ".mov", ".avi"}
MEMORY_FILE = Path.cwd() / ".enhance_meeting_cache.json"

_GPU = torch.cuda.is_available()


# ---------------------------------------------------------------------------
# Cache
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
    """Extrae/convierte a WAV 48 kHz mono. Usa hwaccel CUDA si disponible."""
    def _attempt(use_gpu: bool) -> bool:
        try:
            inp = ffmpeg.input(str(src), hwaccel="cuda") if use_gpu else ffmpeg.input(str(src))
            (
                ffmpeg.output(inp.audio, str(dst), acodec="pcm_s16le", ar=48000, ac=1)
                .run(overwrite_output=True, capture_stdout=True, capture_stderr=True)
            )
            return True
        except ffmpeg.Error:
            return False

    return (_GPU and _attempt(True)) or _attempt(False)


# Alias para compatibilidad con imports existentes
extract_to_wav16k = extract_to_wav


def measure_lufs(wav: Path) -> float:
    """Devuelve el loudness integrado en LUFS. -70 si silencio o error."""
    try:
        _, stderr = (
            ffmpeg.input(str(wav))
            .output("-", format="null", af="loudnorm=print_format=json")
            .run(capture_stdout=True, capture_stderr=True)
        )
        m = re.search(rb'"input_i"\s*:\s*"([^"]+)"', stderr)
        if m and m.group(1) != b"-inf":
            return float(m.group(1))
    except (ffmpeg.Error, ValueError):
        pass
    return -70.0


def normalize_lufs(src: Path, dst: Path) -> bool:
    """Aplica ganancia para llevar el audio a TARGET_LUFS."""
    current = measure_lufs(src)
    if current <= -69.0:          # silencio - copiar sin tocar
        shutil.copy2(src, dst)
        return True

    gain_db = max(min(TARGET_LUFS - current, 30.0), -30.0)
    try:
        (
            ffmpeg.input(str(src))
            .output(str(dst), af=f"volume={gain_db:.2f}dB")
            .run(overwrite_output=True, capture_stdout=True, capture_stderr=True)
        )
    except ffmpeg.Error:
        shutil.copy2(src, dst)
    return True


def to_aac(src: Path, dst: Path, bitrate: str = "192k") -> bool:
    """Comprime WAV a M4A AAC para subida y almacenamiento."""
    try:
        (
            ffmpeg.input(str(src))
            .output(str(dst), acodec="aac", audio_bitrate=bitrate)
            .run(overwrite_output=True, capture_stdout=True, capture_stderr=True)
        )
        return True
    except ffmpeg.Error:
        return False


# Alias para compatibilidad con enhance_video_audio imports
to_m4a = to_aac


# ---------------------------------------------------------------------------
# Procesamiento de un archivo
# ---------------------------------------------------------------------------

def process(src: Path, cv: ClearVoice, m4a: bool = True, skip_normalize: bool = False) -> Path | None:
    """
    Procesa src con el pipeline enhance.
    Por defecto guarda como M4A AAC (m4a=True). Pasar m4a=False para WAV.
    """
    d = src.parent
    stem = src.stem

    tmp_raw  = d / f"{stem}._tmp_raw.wav"
    tmp_norm = d / f"{stem}._tmp_norm.wav"
    tmp_enh  = d / f"{stem}._tmp_enh.wav"
    out = d / f"{stem}_enhanced.{'m4a' if m4a else 'wav'}"

    try:
        gpu_tag = " (GPU)" if _GPU else ""
        print(f"  [1/4] Extrayendo WAV 48kHz{gpu_tag}...")
        if not extract_to_wav(src, tmp_raw):
            raise RuntimeError("ffmpeg no pudo extraer el audio")

        if skip_normalize:
            print("  [2/4] Normalizacion saltada (--skip-normalize)")
            shutil.copy2(tmp_raw, tmp_norm)
        else:
            print("  [2/4] Normalizando LUFS...")
            normalize_lufs(tmp_raw, tmp_norm)

        print(f"  [3/4] {MODEL}...")
        enhanced = cv(input_path=str(tmp_norm), online_write=False)
        cv.write(enhanced, output_path=str(tmp_enh))

        if m4a:
            print("  [4/4] Convirtiendo a AAC M4A...")
            if not to_aac(tmp_enh, out):
                raise RuntimeError("ffmpeg no pudo convertir a AAC")
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
        description="Limpia audio de reuniones en sala para transcripcion",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  %(prog)s                      # todos los archivos del directorio
  %(prog)s reunion.mp4          # un archivo (salida: M4A por defecto)
  %(prog)s reunion.mp4 --wav    # salida en WAV 48kHz
  %(prog)s reunion.mp4 --force  # reprocesar aunque este en cache
        """,
    )
    parser.add_argument(
        "files", nargs="*",
        help="Archivos a procesar (default: todos los soportados en el directorio)",
    )
    parser.add_argument(
        "--wav", action="store_true",
        help="Guardar salida como WAV 48kHz en vez de M4A AAC 192k",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Reprocesar aunque ya este en cache",
    )
    parser.add_argument(
        "--skip-normalize", action="store_true",
        help="Saltar normalizacion LUFS (audio ya normalizado)",
    )
    args = parser.parse_args()

    m4a = not args.wav

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

    gpu_label = f"GPU ({torch.cuda.get_device_name(0)})" if _GPU else "CPU"
    print(f"Encontrados:   {len(files)}")
    print(f"Ya en cache:   {len(files) - len(pending)}")
    print(f"Por procesar:  {len(pending)}")
    print(f"Modelo:        {MODEL}  |  Salida: {'WAV 48kHz' if args.wav else 'M4A AAC 192k'}  |  {gpu_label}")

    if not pending:
        print("\nTodo procesado. Usa --force para reprocesar.")
        sys.exit(0)

    print(f"\nCargando {MODEL}...")
    cv = ClearVoice(task="speech_enhancement", model_names=[MODEL])

    ok, failed = 0, []
    for i, f in enumerate(pending, 1):
        print(f"\n[{i}/{len(pending)}] {f.name}")
        result = process(f, cv, m4a, skip_normalize=args.skip_normalize)
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
