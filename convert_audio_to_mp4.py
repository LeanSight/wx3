"""
Convierte audio a MP4 con video negro usando ffmpeg-python.

GPU NVIDIA (NVENC h264) si disponible via torch.cuda, CPU fallback (libx264 ultrafast).
El video negro se genera con lavfi y se codifica al preset mas rapido posible.

Uso:
  python convert_audio_to_mp4.py audio.m4a
  python convert_audio_to_mp4.py audio.wav salida.mp4
"""

import sys
from pathlib import Path

import ffmpeg
import torch
from enhance_audio import _GPU

VIDEO_W   = 854
VIDEO_H   = 480
VIDEO_FPS = 30


def convert(audio_path: Path, output_path: Path) -> bool:
    """
    Genera un MP4 con video negro + audio.
    WAV se recodifica a AAC 192k; otros formatos se copian sin recodificar.
    Retorna True si exitoso.
    """
    is_wav = audio_path.suffix.lower() == ".wav"

    black = ffmpeg.input(
        f"color=c=black:s={VIDEO_W}x{VIDEO_H}:r={VIDEO_FPS}",
        f="lavfi",
    )
    audio = ffmpeg.input(str(audio_path))

    if _GPU:
        video_opts = {
            "vcodec": "h264_nvenc",
            "preset": "p1",    # preset mas rapido de NVENC
            "gpu":    0,
        }
    else:
        video_opts = {
            "vcodec":  "libx264",
            "preset":  "ultrafast",
            "crf":     35,
        }

    audio_opts = {"acodec": "aac", "audio_bitrate": "192k"} if is_wav \
            else {"acodec": "copy"}

    try:
        (
            ffmpeg
            .output(
                black.video, audio.audio, str(output_path),
                **video_opts,
                **audio_opts,
                movflags="+faststart",
                shortest=None,
            )
            .run(overwrite_output=True, capture_stdout=True, capture_stderr=True)
        )
        return True
    except ffmpeg.Error as e:
        tail = e.stderr.decode(errors="replace")[-600:]
        print(f"  ERROR ffmpeg:\n{tail}")
        return False


def main():
    if len(sys.argv) < 2:
        print("Uso: python convert_audio_to_mp4.py <audio> [salida.mp4]")
        sys.exit(1)

    audio_path = Path(sys.argv[1])
    if not audio_path.exists():
        print(f"ERROR: no se encontro {audio_path}")
        sys.exit(1)

    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else \
        audio_path.parent / f"{audio_path.stem}_converted.mp4"

    is_wav    = audio_path.suffix.lower() == ".wav"
    gpu_label = f"GPU ({torch.cuda.get_device_name(0)})" if _GPU else "CPU"
    encoder   = "h264_nvenc p1" if _GPU else "libx264 ultrafast"

    print(f"Entrada:  {audio_path.name}")
    print(f"Salida:   {output_path.name}")
    print(f"Video:    {VIDEO_W}x{VIDEO_H} negro @ {VIDEO_FPS}fps  |  {encoder}  |  {gpu_label}")
    print(f"Audio:    {'AAC 192k (recodificado desde WAV)' if is_wav else 'copy'}")
    print()

    ok = convert(audio_path, output_path)
    if ok:
        mb = output_path.stat().st_size / (1024 * 1024)
        print(f"OK -> {output_path.name} ({mb:.1f} MB)")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
