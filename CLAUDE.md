# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Critical Constraint: ASCII-Only Output

**Never use non-ASCII characters in any Python code that produces output.** The Windows console (cp1252) crashes on any non-ASCII in `print()`, `logging`, argparse help/description/epilog, f-strings, or docstrings that flow to stdout/stderr. This means no arrows (`->` is fine, `->` unicode arrow is not), no accented characters, no box-drawing characters, no smart quotes. Use only plain ASCII (0-127) in all text that could be printed.

## Environment

Python 3.11 (see `.python-version`). The virtual environment lives in `.pixi/envs/default/`. Activate with:

```bash
source .pixi/envs/default/Scripts/activate  # Git Bash on Windows
# or
.pixi/envs/default/Scripts/activate.bat     # Windows cmd
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Requires `ffmpeg` on PATH and a Hugging Face token for diarization (`HF_TOKEN` env var or `--token` flag).

## Running Commands

```bash
# Transcription only
python wx3.py transcribe file.mp3

# Full pipeline (transcription + speaker diarization)
python wx3.py process interview.mp4 --token hf_...

# Diarization only
python wx3.py diarize meeting.wav --token hf_...

# Convert JSON output to SRT/VTT post-processing
python output_convert.py transcription.json -f srt

# Audio enhancement with ClearVoice (MossFormer2_SE_48K)
python enhance_audio.py input.wav

# Full enhance + transcribe pipeline (AssemblyAI)
python enhance_and_transcribe.py input.mp4

# Verify system dependencies (torch, pyannote, ffmpeg)
python verify_dependencies.py
```

## Running Tests

```bash
# Run all tests
pytest

# Run a single test file
pytest test_sentence_grouping.py

# Run a specific test
pytest test_sentence_grouping.py::TestClassName::test_method_name -v
```

Tests live in the project root as `test_*.py` files. There are no integration tests that require real audio files in CI.

## Architecture

WX3 is a modular audio/video transcription and speaker diarization pipeline. All modules are flat in the project root with no package structure.

**Data flow for `wx3.py process`:**

```
input_media.py  ->  diarization.py  ->  transcription.py  ->  alignment.py
(load audio)        (PyAnnote)          (Whisper)              (match speakers
                    speaker segments    word chunks             to text chunks)
                                                              -> sentence_grouping.py
                                                              -> output_formatters.py
                                                                 (SRT/VTT/TXT/JSON)
```

**Key modules:**

- `wx3.py` - Typer CLI with 4 commands: `transcribe`, `diarize`, `process`, `manage_cache`
- `processor.py` - Orchestration; calls diarization, transcription, alignment, and formatting
- `pipelines.py` - LRU-cached pipeline creation (maxsize=2 for Whisper, 1 for PyAnnote)
- `constants.py` - All enums (`Device`, `Task`, `SubtitleFormat`, `GroupingMode`), defaults, and help strings
- `lazy_loading.py` - Defers heavy imports (torch, pyannote) until first use, with timing
- `input_media.py` - Audio/video loading via PyAV with a 2GB/20-entry in-memory cache
- `alignment.py` - O(n+m) sliding window to match PyAnnote speaker segments to Whisper chunks
- `sentence_grouping.py` - Groups chunks into subtitle segments by sentences (default) or by speaker only (`--long`)

**Enhancement pipeline (separate from wx3.py):**

- `enhance_audio.py` - ClearVoice speech enhancement; caches results in `.enhance_meeting_cache.json`
- `enhance_video_audio.py` - Wraps `enhance_audio.py` for video input
- `enhance_and_transcribe.py` - Chains enhancement -> AssemblyAI transcription -> SRT output
- `assembly_transcribe.py` / `assemblyai_main.py` - AssemblyAI API integration (alternative to Whisper)

## Coding Conventions

- **Pathlib throughout**: Always use `pathlib.Path`, never raw string paths
- **TypedDict for structured data**: `AudioData`, `TranscriptChunk`, `SpeakerSegment` etc.
- **Dataclasses for results**: `TranscriptionResult`, `DiarizationResult` are immutable result containers
- **Per-module loggers**: `logger = logging.getLogger(__name__)` at module level; configure via `logging_config.py`
- **All defaults in `constants.py`**: Do not hardcode values that are already defined there
- **Environment variables for secrets**: `HF_TOKEN`, `ASSEMBLY_AI_KEY` - never in code
- **File I/O**: Always `encoding="utf-8"` and `ensure_ascii=False` for JSON
