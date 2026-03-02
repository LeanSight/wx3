import subprocess
from pathlib import Path
from typing import Optional, Callable

def generate_black_video(
    audio_path: Path,
    video_path: Path,
    width: int = 1920,
    height: int = 1080,
    fps: int = 24,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> bool:
    """Generate a black video with the given audio."""
    # Command: ffmpeg -f lavfi -i color=c=black:s=1920x1080:r=24 -i audio.m4a -shortest -c:v libx264 -tune stillimage -pix_fmt yuv420p -c:a copy out.mp4
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"color=c=black:s={width}x{height}:r={fps}",
        "-i", str(audio_path),
        "-shortest",
        "-c:v", "libx264",
        "-tune", "stillimage",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", # Re-encode to be safe
        str(video_path)
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg error: {result.stderr}")
        return True
    except FileNotFoundError:
        raise RuntimeError("ffmpeg not found. Please install ffmpeg.")


def compress_video(
    in_path: Path,
    out_path: Path,
    crf: int = 23,
    preset: str = "medium",
    progress_callback: Optional[Callable[[int, int], None]] = None,
    audio_path: Optional[Path] = None,
) -> bool:
    """Compress video using libx264, optionally replacing audio."""
    cmd = ["ffmpeg", "-y"]
    
    if audio_path:
        # Use separate audio source
        cmd.extend(["-i", str(in_path), "-i", str(audio_path), "-map", "0:v:0", "-map", "1:a:0", "-shortest"])
    else:
        # Use audio from video source
        cmd.extend(["-i", str(in_path)])
        
    cmd.extend([
        "-c:v", "libx264",
        "-crf", str(crf),
        "-preset", preset,
        "-c:a", "aac", # Re-encode audio to ensures compatibility
        str(out_path)
    ])
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg error: {result.stderr}")
        return True
    except FileNotFoundError:
        raise RuntimeError("ffmpeg not found. Please install ffmpeg.")
