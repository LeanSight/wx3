"""
compress_video.py
-----------------
Comprime un video al % objetivo del tamaño original con:
  - Normalización LUFS del audio (EBU R128, -23 LUFS)
  - Detección automática de aceleración de hardware
  - Barra de progreso Rich en tiempo real
  - ffmpeg-python nativo (sin subprocess manual)

Compatible con Google Photos (H.264/AAC en MP4).

Uso:
    python compress_video.py video.mp4
    python compress_video.py video.mp4 --ratio 0.40
    python compress_video.py video.mp4 --encoder cpu
    python compress_video.py video.mp4 --no-normalize
"""

from __future__ import annotations

import argparse
import glob
import logging
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import ffmpeg
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

# ---------------------------------------------------------------------------
# Logging & consola
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)
console = Console()

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

AUDIO_BITRATE_KBPS = 128
GOOGLE_PHOTOS_PIXEL_FORMAT = "yuv420p"

# LUFS — estándar EBU R128 para broadcast
TARGET_LUFS = -23.0
LUFS_SILENCE_THRESHOLD = -69.0
MAX_GAIN_DB = 30.0

# Encoders HW por prioridad de detección
# Los extra_kwargs se pasan directamente a ffmpeg-python como **kwargs
HW_ENCODERS: list[tuple[str, str, dict]] = [
    ("h264_nvenc", "NVIDIA NVENC", {"preset": "p4", "rc": "vbr"}),
    ("h264_amf", "AMD AMF", {"quality": "balanced"}),
    ("h264_qsv", "Intel QuickSync", {"preset": "medium"}),
    ("h264_videotoolbox", "Apple VideoToolbox", {}),
]
CPU_ENCODER: tuple[str, str, dict] = ("libx264", "CPU x264", {"preset": "medium"})

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class VideoInfo:
    path: Path
    duration_s: float
    size_bytes: int
    width: int
    height: int
    fps: str
    has_audio: bool = True


@dataclass
class EncoderInfo:
    ffmpeg_name: str
    label: str
    extra_kwargs: dict = field(default_factory=dict)

    def __str__(self) -> str:
        return f"{self.label} ({self.ffmpeg_name})"


@dataclass
class LufsInfo:
    """Resultado de la medición LUFS y la ganancia calculada."""

    measured_lufs: float
    gain_db: float
    is_silent: bool

    @classmethod
    def from_measured(cls, lufs: float) -> LufsInfo:
        is_silent = lufs <= LUFS_SILENCE_THRESHOLD
        if is_silent:
            gain = 0.0
        else:
            raw_gain = TARGET_LUFS - lufs
            gain = max(min(raw_gain, MAX_GAIN_DB), -MAX_GAIN_DB)
        return cls(measured_lufs=lufs, gain_db=gain, is_silent=is_silent)

    @classmethod
    def noop(cls) -> LufsInfo:
        """LufsInfo sin ningún ajuste (normalización desactivada)."""
        return cls(measured_lufs=-70.0, gain_db=0.0, is_silent=True)


def expand_inputs(inputs: list[Path]) -> list[Path]:
    """Expande patrones glob y retorna lista de archivos existentes."""
    expanded = []
    for inp in inputs:
        pattern = str(inp)
        if any(c in pattern for c in "*?["):
            for match in glob.glob(pattern):
                p = Path(match)
                if p.exists():
                    expanded.append(p)
        if not expanded:
            if inp.exists():
                expanded.append(inp)
        else:
            log.warning(" patron no coincide: %s", pattern)
    return expanded


# ---------------------------------------------------------------------------
# Probe — ffmpeg-python
# ---------------------------------------------------------------------------


def probe_video(path: Path) -> VideoInfo:
    """Extrae metadata del video con ffprobe via ffmpeg-python."""
    try:
        data = ffmpeg.probe(str(path))
    except ffmpeg.Error as e:
        raise RuntimeError(
            f"ffprobe falló para '{path.name}':\n{e.stderr.decode(errors='replace')}"
        )

    fmt = data["format"]
    video_stream = next(
        (s for s in data["streams"] if s["codec_type"] == "video"), None
    )
    if video_stream is None:
        raise RuntimeError(f"No se encontró stream de video en '{path.name}'")

    has_audio = any(s["codec_type"] == "audio" for s in data["streams"])

    return VideoInfo(
        path=path,
        duration_s=float(fmt["duration"]),
        size_bytes=int(fmt["size"]),
        width=int(video_stream["width"]),
        height=int(video_stream["height"]),
        fps=video_stream.get("avg_frame_rate", "unknown"),
        has_audio=has_audio,
    )


# ---------------------------------------------------------------------------
# Medición LUFS — patrón extraído de wx4/audio_normalize.py
# ---------------------------------------------------------------------------


def measure_audio_lufs(path: Path) -> float:
    """
    Mide la loudness integrada del audio con el filtro loudnorm de FFmpeg.
    Retorna -70.0 en silencio o cualquier error.
    """
    try:
        _, stderr = (
            ffmpeg.input(str(path))
            .audio.output("-", format="null", af="loudnorm=print_format=json")
            .run(capture_stdout=True, capture_stderr=True)
        )
        m = re.search(rb'"input_i"\s*:\s*"([^"]+)"', stderr)
        if m and m.group(1) != b"-inf":
            val = float(m.group(1))
            if val == val:  # NaN check: NaN != NaN
                return val
    except (ffmpeg.Error, ValueError):
        pass
    return -70.0


# ---------------------------------------------------------------------------
# Detección de hardware — ffmpeg-python
# ---------------------------------------------------------------------------


def _encoder_works(encoder_name: str) -> bool:
    """Prueba el encoder generando 1 frame nulo. Rápido (~1s por encoder)."""
    try:
        (
            ffmpeg.input("nullsrc=s=64x64:d=0.1", f="lavfi")
            .output("-", vcodec=encoder_name, vframes=1, f="null")
            .run(capture_stdout=True, capture_stderr=True)
        )
        return True
    except (ffmpeg.Error, FileNotFoundError):
        return False


def detect_best_encoder(force: str | None = None) -> EncoderInfo:
    """
    Detecta y retorna el mejor encoder disponible.
    `force` acepta 'cpu' o el nombre ffmpeg de un encoder HW específico.
    """
    if force == "cpu":
        name, label, kwargs = CPU_ENCODER
        log.info("Encoder forzado: CPU")
        return EncoderInfo(name, label, kwargs)

    log.info("Detectando aceleracion de hardware disponible...")
    for ffmpeg_name, label, extra_kwargs in HW_ENCODERS:
        if force and force != ffmpeg_name:
            continue
        if _encoder_works(ffmpeg_name):
            enc = EncoderInfo(ffmpeg_name, label, extra_kwargs)
            log.info("OK Disponible: %s", enc)
            return enc
        log.debug("No disponible: %s (%s)", label, ffmpeg_name)

    log.info("Sin aceleracion HW detectada -> CPU (libx264)")
    name, label, kwargs = CPU_ENCODER
    return EncoderInfo(name, label, kwargs)


# ---------------------------------------------------------------------------
# Cálculo de bitrate
# ---------------------------------------------------------------------------


def calculate_video_bitrate(info: VideoInfo, target_ratio: float) -> int:
    """Calcula el bitrate de video en kbps para alcanzar el ratio objetivo."""
    target_bytes = info.size_bytes * target_ratio
    total_kbps = (target_bytes * 8) / (info.duration_s * 1000)
    return max(int(total_kbps) - AUDIO_BITRATE_KBPS, 100)  # mínimo 100 kbps


# ---------------------------------------------------------------------------
# Progress Rich — patrón estándar 2026
# ---------------------------------------------------------------------------


def _make_progress() -> Progress:
    """
    Barra de progreso Rich transient (desaparece al terminar).
    Patrón estándar para pipelines fire-and-forget en 2026.
    """
    return Progress(
        SpinnerColumn(),
        TextColumn("[bold cyan]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    )


def _run_with_progress(
    stream,
    duration_s: float,
    progress: Progress | None,
    description: str,
    progress_callback: Callable[[int, int], None] | None = None,
) -> None:
    """
    Ejecuta un stream ffmpeg-python.

    Si progress_callback está definido, se usa para reportar progreso.
    Si no hay callback ni progress, no se muestra progreso.
    """
    process = stream.global_args("-progress", "pipe:1", "-nostats").run_async(
        pipe_stdout=True, pipe_stderr=True
    )

    while True:
        line = process.stdout.readline().decode("utf-8", errors="replace").strip()

        if not line:
            if process.poll() is not None:
                break
            continue

        key, _, value = line.partition("=")
        if key == "out_time_ms":
            try:
                elapsed_s = int(value) / 1_000_000  # microsegundos → segundos
                percent = min(int(elapsed_s / duration_s * 100), 99)
                if progress_callback:
                    progress_callback(percent, 100)
            except ValueError:
                pass
        elif key == "progress" and value == "end":
            if progress_callback:
                progress_callback(100, 100)
            break

    process.wait()

    if process.returncode not in (0, None):
        stderr_tail = process.stderr.read().decode("utf-8", errors="replace")[-600:]
        raise RuntimeError(
            f"FFmpeg falló (código {process.returncode}):\n{stderr_tail}"
        )


# ---------------------------------------------------------------------------
# Construcción de streams — ffmpeg-python
# ---------------------------------------------------------------------------


def _apply_lufs_filter(audio_stream, lufs: LufsInfo):
    """Aplica el filtro volume si la ganancia es significativa (> 0.1 dB)."""
    if abs(lufs.gain_db) > 0.1:
        return audio_stream.filter("volume", f"{lufs.gain_db:.2f}dB")
    return audio_stream


def _build_encode_stream(
    info: VideoInfo,
    lufs: LufsInfo,
    encoder: EncoderInfo,
    video_bitrate_kbps: int,
    output_path: Path,
    pass_number: int | None = None,
    passlogfile: str | None = None,
) -> object:
    """
    Construye el stream ffmpeg-python para un paso de codificación.

    - pass_number=None → 1-pass HW (audio + video)
    - pass_number=1    → primer paso 2-pass (solo video, salida nula)
    - pass_number=2    → segundo paso 2-pass (video + audio con LUFS)
    """
    null_out = "NUL" if sys.platform == "win32" else "/dev/null"
    inp = ffmpeg.input(str(info.path))

    # Opciones de video comunes
    video_kwargs: dict = {
        "vcodec": encoder.ffmpeg_name,
        **{"b:v": f"{video_bitrate_kbps}k"},
        **encoder.extra_kwargs,
        "pix_fmt": GOOGLE_PHOTOS_PIXEL_FORMAT,
    }

    if pass_number is not None:
        video_kwargs["pass"] = pass_number
    if passlogfile is not None:
        video_kwargs["passlogfile"] = passlogfile

    if pass_number == 1:
        # Primera pasada: solo video → null, sin audio
        return ffmpeg.output(
            inp.video, null_out, f="null", **video_kwargs
        ).overwrite_output()

    # Pasada 2 o 1-pass: incluye audio con LUFS + faststart
    video_kwargs["movflags"] = "+faststart"
    audio_kwargs: dict = {"acodec": "aac", **{"b:a": f"{AUDIO_BITRATE_KBPS}k"}}

    if info.has_audio:
        audio = _apply_lufs_filter(inp.audio, lufs)
        return ffmpeg.output(
            inp.video, audio, str(output_path), **video_kwargs, **audio_kwargs
        ).overwrite_output()
    else:
        return ffmpeg.output(
            inp.video, str(output_path), **video_kwargs
        ).overwrite_output()


# ---------------------------------------------------------------------------
# Compresión principal
# ---------------------------------------------------------------------------


def compress_video(
    info: VideoInfo,
    lufs: LufsInfo,
    encoder: EncoderInfo,
    video_bitrate_kbps: int,
    output_path: Path,
    progress_callback: "Callable[[int, int], None] | None" = None,
) -> None:
    """
    Comprime el video con normalización LUFS integrada como filtro de audio.

    - libx264 (CPU): 2-pass para máxima precisión de tamaño
    - Encoders HW:   1-pass VBR (los drivers HW no soportan 2-pass de forma fiable)

    Args:
        progress_callback: Optional callback(done, total) to report progress.
            When provided, no internal Progress display is created.
    """
    use_two_pass = encoder.ffmpeg_name == "libx264"
    passlogfile = str(output_path.parent / f".{output_path.stem}_ffpass")

    # Los steps NUNCA deben generar Progress. Si no hay callback, no se muestra progreso.
    if use_two_pass:
        pass1 = _build_encode_stream(
            info,
            lufs,
            encoder,
            video_bitrate_kbps,
            output_path,
            pass_number=1,
            passlogfile=passlogfile,
        )
        _run_with_progress(
            pass1,
            info.duration_s,
            None,  # Sin Progress interno
            "Analizando    [pasada 1/2]",
            progress_callback=progress_callback,
        )

        pass2 = _build_encode_stream(
            info,
            lufs,
            encoder,
            video_bitrate_kbps,
            output_path,
            pass_number=2,
            passlogfile=passlogfile,
        )
        _run_with_progress(
            pass2,
            info.duration_s,
            None,
            "Codificando   [pasada 2/2]",
            progress_callback=progress_callback,
        )
    else:
        stream = _build_encode_stream(
            info, lufs, encoder, video_bitrate_kbps, output_path
        )
        _run_with_progress(
            stream,
            info.duration_s,
            None,
            "Codificando   [hardware]  ",
            progress_callback=progress_callback,
        )

    # Limpieza de archivos temporales de 2-pass
    for suffix in (".log", ".log.mbtree"):
        p = Path(passlogfile + "-0" + suffix)
        if p.exists():
            p.unlink()


# ---------------------------------------------------------------------------
# Resumen final
# ---------------------------------------------------------------------------


def print_summary(
    info: VideoInfo,
    lufs: LufsInfo,
    output_path: Path,
    target_ratio: float,
) -> None:
    original_mb = info.size_bytes / 1_048_576
    final_bytes = output_path.stat().st_size
    final_mb = final_bytes / 1_048_576
    actual_ratio = final_bytes / info.size_bytes

    if lufs.is_silent or not info.has_audio:
        audio_note = "sin normalización"
    else:
        audio_note = (
            f"{lufs.measured_lufs:.1f} LUFS → {TARGET_LUFS:.0f} LUFS  "
            f"({lufs.gain_db:+.1f} dB)"
        )

    console.print()
    console.print("=" * 54)
    console.print(f"  📁 Original:  {original_mb:.1f} MB")
    console.print(
        f"  🎯 Objetivo:  {original_mb * target_ratio:.1f} MB  ({target_ratio * 100:.0f}%)"
    )
    console.print(f"  ✅ Resultado: {final_mb:.1f} MB  ({actual_ratio * 100:.1f}%)")
    console.print(f"  🔊 LUFS:      {audio_note}")
    console.print(f"  📄 Archivo:   {output_path.name}")
    console.print("=" * 54)
    console.print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Comprime video para Google Photos: LUFS + HW + progreso en tiempo real.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "input",
        type=Path,
        nargs="+",
        help="Video(s) de entrada (acepta glob, ej: *.mp4)",
    )
    parser.add_argument(
        "--ratio",
        type=float,
        default=0.40,
        help="Fracción del tamaño original (0.40 = 40%%)",
    )
    parser.add_argument(
        "--encoder",
        default=None,
        help="Forzar encoder: 'cpu', 'h264_nvenc', 'h264_amf', 'h264_qsv'",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Ruta de salida (por defecto: <nombre>_compressed.mp4)",
    )
    parser.add_argument(
        "--no-normalize",
        action="store_true",
        help="Omitir normalización LUFS del audio",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # Expandir globs y validar
    input_paths = expand_inputs(args.input)
    if not input_paths:
        log.error("No se encontraron archivos validos")
        sys.exit(1)

    # Validar --output con multiples inputs
    if args.output and len(input_paths) > 1:
        log.error("--output no es valido con multiples archivos de entrada")
        sys.exit(1)

    # Procesar cada video
    for input_path in input_paths:
        if not input_path.exists():
            log.error("Archivo no encontrado: %s", input_path)
            continue

        output_path = (
            args.output
            if args.output
            else (input_path.parent / f"{input_path.stem}_compressed.mp4")
        )

        # 1. Analizar video
        log.info("Analizando: %s", input_path.name)
        info = probe_video(input_path)
        log.info(
            "Resolucion: %dx%d | %.1fs | %.1f MB",
            info.width,
            info.height,
            info.duration_s,
            info.size_bytes / 1_048_576,
        )

        # 2. Medir LUFS del audio
        if args.no_normalize or not info.has_audio:
            lufs = LufsInfo.noop()
            reason = (
                "sin audio" if not info.has_audio else "desactivada por --no-normalize"
            )
            log.info("Normalizacion LUFS: %s", reason)
        else:
            log.info("Midiendo loudness del audio...")
            measured = measure_audio_lufs(input_path)
            lufs = LufsInfo.from_measured(measured)
            if lufs.is_silent:
                log.info("Audio silencioso -> sin normalizacion")
            else:
                log.info(
                    "LUFS: %.1f -> %.0f (ganancia: %+.1f dB)",
                    lufs.measured_lufs,
                    TARGET_LUFS,
                    lufs.gain_db,
                )

        # 3. Detectar encoder (mismo encoder para todos)
        encoder = detect_best_encoder(force=args.encoder)

        # 4. Calcular bitrate objetivo
        video_bitrate = calculate_video_bitrate(info, args.ratio)
        log.info(
            "Bitrate -> video: %d kbps | audio: %d kbps",
            video_bitrate,
            AUDIO_BITRATE_KBPS,
        )

        # 5. Comprimir
        log.info("Comprimiendo con %s -> %s", encoder, output_path.name)
        compress_video(info, lufs, encoder, video_bitrate, output_path)

        # 6. Resumen
        print_summary(info, lufs, output_path, args.ratio)


if __name__ == "__main__":
    main()
