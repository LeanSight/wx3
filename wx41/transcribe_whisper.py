import json
import subprocess
from pathlib import Path
from typing import Optional, Tuple, Callable
import torch
from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline
import tempfile

def transcribe_whisper(
    audio: Path,
    api_key: Optional[str] = None,
    lang: Optional[str] = None,
    speakers: Optional[int] = None,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    model: str = "openai/whisper-base",
) -> Tuple[Path, Path]:
    if progress_callback:
        progress_callback(0, 3)

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", str(audio), "-ar", "16000", "-ac", "1", str(tmp_path)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg error: {result.stderr}")
    except FileNotFoundError:
        raise RuntimeError("ffmpeg not found. Please install ffmpeg.")

    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32

    if progress_callback:
        progress_callback(1, 3)

    model_id = model
    processor = AutoProcessor.from_pretrained(model_id)
    model = AutoModelForSpeechSeq2Seq.from_pretrained(
        model_id,
        torch_dtype=torch_dtype,
        low_cpu_mem_usage=True,
    )
    model.to(device)

    pipe = pipeline(
        "automatic-speech-recognition",
        model=model,
        tokenizer=processor.tokenizer,
        feature_extractor=processor.feature_extractor,
        torch_dtype=torch_dtype,
        device=device,
        return_timestamps=True,
    )

    if progress_callback:
        progress_callback(2, 3)

    result = pipe(str(tmp_path), language=lang if lang else "es")

    words = []
    if "chunks" in result:
        for chunk in result["chunks"]:
            words.append({
                "text": chunk.get("text", "").strip(),
                "start": chunk.get("timestamp", [0, 0])[0] if chunk.get("timestamp") else 0,
                "end": chunk.get("timestamp", [0, 0])[1] if chunk.get("timestamp") else 0,
                "confidence": 1.0,
                "speaker": "A"
            })

    json_path = audio.parent / f"{audio.stem}_whisper.json"
    json_path.write_text(json.dumps(words, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = []
    for w in words:
        s = int(w["start"])
        h, rem = divmod(s, 3600)
        m, sec = divmod(rem, 60)
        ts = f"{h:02d}:{m:02d}:{sec:02d}" if h else f"{m:02d}:{sec:02d}"
        lines.append(f"[{ts}] {w['speaker']}: {w['text']}")

    txt_path = audio.parent / f"{audio.stem}_whisper.txt"
    txt_path.write_text("\n".join(lines), encoding="utf-8")

    if progress_callback:
        progress_callback(3, 3)

    tmp_path.unlink(missing_ok=True)

    return txt_path, json_path
