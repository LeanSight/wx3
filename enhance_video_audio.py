"""
Extraer audio de videos y mejorarlo con ClearVoice.
"""

from clearvoice import ClearVoice
from pathlib import Path
import subprocess
import sys
import json
import argparse

# Configuración
WORK_DIR = Path.cwd()  # Directorio desde donde se ejecuta
MODEL = "MossFormer2_SE_48K"  # Mejor calidad, requiere 48kHz
MEMORY_FILE = WORK_DIR / ".audio_enhance_memory.json"


def load_memory() -> dict:
    """Carga el registro de archivos procesados."""
    if MEMORY_FILE.exists():
        try:
            return json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def save_memory(memory: dict):
    """Guarda el registro de archivos procesados."""
    MEMORY_FILE.write_text(json.dumps(memory, indent=2, ensure_ascii=False), encoding="utf-8")


def get_file_key(video_path: Path) -> str:
    """Genera clave única: nombre + tamaño + fecha modificación."""
    stat = video_path.stat()
    return f"{video_path.name}|{stat.st_size}|{stat.st_mtime}"


def is_processed(video_path: Path, memory: dict) -> bool:
    """Verifica si el video ya fue procesado (y no modificado)."""
    key = get_file_key(video_path)
    return key in memory


def extract_audio(video_path: Path, audio_path: Path) -> bool:
    """Extrae audio de video a WAV 48kHz."""
    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "48000",
        str(audio_path)
    ]
    result = subprocess.run(cmd, capture_output=True)
    return result.returncode == 0


def convert_to_m4a(wav_path: Path, m4a_path: Path) -> bool:
    """Convierte WAV a M4A (AAC)."""
    cmd = [
        "ffmpeg", "-y",
        "-i", str(wav_path),
        "-acodec", "aac",
        "-b:a", "192k",
        str(m4a_path)
    ]
    result = subprocess.run(cmd, capture_output=True)
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(description='Extraer y mejorar audio de videos')
    parser.add_argument('files', nargs='*', help='Archivos a procesar (default: todos los .mp4 del directorio)')
    args = parser.parse_args()

    # Cargar memoria de proceso
    memory = load_memory()

    # Limpiar memoria: eliminar entradas de archivos que ya no existen
    existing_files = {f.name for f in WORK_DIR.glob("*.mp4")}
    old_keys = list(memory.keys())
    for key in old_keys:
        filename = key.split("|")[0]
        if filename not in existing_files:
            del memory[key]
    save_memory(memory)

    # Obtener lista de videos a procesar
    if args.files:
        all_videos = [Path(f) for f in args.files]
        all_videos = [v for v in all_videos if v.exists() and v.suffix.lower() in ['.mp4', '.m4a']]
        if not all_videos:
            print("No se encontraron archivos válidos (.mp4 o .m4a)")
            return
    else:
        all_videos = list(WORK_DIR.glob("*.mp4"))
        if not all_videos:
            print("No se encontraron videos .mp4")
            return

    # Filtrar videos ya procesados
    videos = [v for v in all_videos if not is_processed(v, memory)]

    print(f"Total archivos: {len(all_videos)}")
    print(f"Ya procesados: {len(all_videos) - len(videos)}")
    print(f"Por procesar: {len(videos)}")

    if not videos:
        print("Todos los videos ya fueron procesados.")
        return

    # Inicializar ClearVoice UNA vez
    print(f"\nCargando modelo {MODEL}...")
    cv = ClearVoice(task="speech_enhancement", model_names=[MODEL])

    processed = 0
    failed = []

    for video in videos:
        print(f"\nProcesando: {video}")

        work_dir = video.parent.resolve()

        # Rutas
        temp_audio = work_dir / f"{video.stem}_audio.wav"
        temp_enhanced = work_dir / f"{video.stem}_audio_enhanced.wav"
        final_audio = work_dir / f"{video.stem}_audio_enhanced.m4a"

        # 1. Extraer audio
        print("  Extrayendo audio...")
        if not extract_audio(video, temp_audio):
            print("  ERROR: No se pudo extraer audio")
            failed.append(video.name)
            continue

        # 2. Mejorar audio
        print("  Mejorando audio...")
        try:
            output = cv(input_path=str(temp_audio), online_write=False)
            cv.write(output, output_path=str(temp_enhanced))
        except Exception as e:
            print(f"  ERROR: {e}")
            failed.append(video.name)
            temp_audio.unlink(missing_ok=True)
            continue

        # 3. Convertir a M4A
        print("  Convirtiendo a M4A...")
        if not convert_to_m4a(temp_enhanced, final_audio):
            print("  ERROR: No se pudo convertir a M4A")
            failed.append(video.name)
            temp_audio.unlink(missing_ok=True)
            temp_enhanced.unlink(missing_ok=True)
            continue

        # 4. Eliminar temporales
        temp_audio.unlink(missing_ok=True)
        temp_enhanced.unlink(missing_ok=True)

        # 5. Registrar en memoria
        memory[get_file_key(video)] = {
            "output": final_audio.name,
            "processed_at": str(Path(final_audio).stat().st_mtime)
        }
        save_memory(memory)

        print(f"  -> {final_audio.name}")
        processed += 1

    # Resumen
    print(f"\n{'='*40}")
    print(f"Procesados: {processed}/{len(videos)}")
    if failed:
        print(f"Fallidos: {', '.join(failed)}")


if __name__ == "__main__":
    main()
