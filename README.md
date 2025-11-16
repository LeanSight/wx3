# WX3 – Audio Transcription & Diarization with Whisper + PyAnnote

**WX3** is a modular Python application for audio/video **transcription**, **speaker diarization**, and **format conversion**, powered by [OpenAI Whisper](https://github.com/openai/whisper) and [pyannote-audio](https://github.com/pyannote/pyannote-audio). Designed for high accuracy, clarity, and multi-format export.

---

## 🚀 Features

- 🎙️ Transcription with Whisper (multilingual support)
- 🧠 Speaker diarization via PyAnnote (auto/fixed speakers)
- 🎞️ Audio extraction from video files
- 📤 Export formats: `SRT`, `VTT`, `TXT`, `JSON`
- 👤 Custom speaker names
- 📝 **Smart subtitle grouping** by sentences or speaker changes
- ⚡ Runs on **CPU** or **CUDA-enabled GPU** *(optional)*

---

## 🔧 Requirements

- **Python 3.11**
- **FFmpeg** (required for PyAV to decode audio/video)
- **Hugging Face Token** (for diarization model access)
- **CUDA (optional)**: for faster processing if available

### Install System Dependencies

```bash
# Ubuntu/Debian
sudo apt install ffmpeg

# macOS (Homebrew)
brew install ffmpeg

# Windows (Chocolatey)
choco install ffmpeg
```

---

## ⚙️ Installation

```bash
git clone https://github.com/LeanSight/wx3.git
cd wx3

# Set up virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

> ⚠️ CUDA is not required, but if available, it will be used automatically for faster processing.

---

## ✅ System Check

You can verify that your environment is ready using:

```bash
python verify_system.py
```

This checks:
- PyTorch and CUDA availability (optional)
- pyannote.audio installation
- ffmpeg availability

---

## 🎬 Basic Usage

### Transcribe Audio or Video

```bash
python wx3.py transcribe file.mp3
```

### Transcribe with Diarization

```bash
python wx3.py process interview.mp4 --token hf_your_token
```

### Transcribe with Long Segments (group only by speaker)

```bash
python wx3.py process interview.mp4 --token hf_your_token --long
```

### Diarization Only

```bash
python wx3.py diarize meeting.wav --token hf_your_token
```

---

## 🔄 Convert Transcriptions

Convert JSON intermediate files to SRT/VTT with smart grouping:

```bash
# Default: group by sentences
python output_convert.py transcription.json -f srt

# Long segments: group only by speaker
python output_convert.py transcription.json -f srt --long
```

Optional flags:

```bash
  -o / --output         Output directory
  --output-name         Output filename (no extension)
  --speaker-names       Comma-separated custom speaker labels
  --long / -lg          Create long segments (group only by speaker)
  --max-chars           Maximum characters per segment (default: 80)
  --max-duration        Maximum duration per segment in seconds (default: 10)
```

---

## ⚙️ CLI Parameters

### Transcription

```
  -m, --model           Whisper model
  -l, --lang            Language code (e.g. 'en', 'es')
  -t, --task            Task: 'transcribe' or 'translate'
  --chunk-length        Duration of chunks in seconds
```

### Subtitle Grouping

```
  --long, -lg           Create long segments (group only by speaker changes)
  --max-chars           Maximum characters per subtitle (default: 80)
  --max-duration        Maximum duration per subtitle in seconds (default: 10)
```

> **Note:** By default, subtitles are grouped by complete sentences with punctuation. Use `--long` for longer segments grouped only by speaker changes.

### Diarization

```
  --diarize             Enable diarization
  --token               HuggingFace token
  --dmodel              PyAnnote model
  --num-speakers        Fixed number of speakers
  --min-speakers        Min speakers
  --max-speakers        Max speakers
```

### Hardware and Performance

```
  -d, --device          'cpu', 'cuda:0', etc.
  -b, --batch-size      Batch size for inference
```

---

## 📁 Project Structure

```
wx3/
├── wx3.py                 # Main CLI entry point
├── transcription.py       # Whisper logic
├── diarization.py         # PyAnnote processing
├── alignment.py           # Speaker merge + alignment
├── sentence_grouping.py   # Subtitle grouping by sentences/speakers
├── input_media.py         # Audio/video loading
├── output_formatters.py   # Format export
├── processor.py           # Processing orchestration
├── pipelines.py           # Pipeline caching
├── verify_dependencies.py # System check (torch, pyannote, ffmpeg)
├── requirements.txt       # Dependencies
├── docs/
│   └── SUBTITLE_GROUPING.md   # Detailed grouping documentation
```

For detailed information about subtitle grouping, see [SUBTITLE_GROUPING.md](./docs/SUBTITLE_GROUPING.md).

---

## 📄 License

Apache 2.0 – see [`LICENSE`](./LICENSE)

---

## 🙏 Acknowledgements

Inspired by [Insanely Fast Whisper](https://github.com/Vaibhavs10/insanely-fast-whisper) and built on Whisper & PyAnnote.
