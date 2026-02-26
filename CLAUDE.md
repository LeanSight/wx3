**Never use non-ASCII characters in any Python code that produces output.** The Windows console (cp1252) crashes on any non-ASCII in `print()`, `logging`, argparse help/description/epilog, f-strings, or docstrings that flow to stdout/stderr. This means no arrows (`->` is fine, `->` unicode arrow is not), no accented characters, no box-drawing characters, no smart quotes. Use only plain ASCII (0-127) in all text that could be printed.

## Environment
Install dependencies:

```bash
pip install -r requirements.txt
```

Tests live in the project root as `test_*.py` files. There are no integration tests that require real audio files in CI.

## Coding Conventions

- **Pathlib throughout**: Always use `pathlib.Path`, never raw string paths
- **TypedDict for structured data**: `AudioData`, `TranscriptChunk`, `SpeakerSegment` etc.
- **Dataclasses for results**: `TranscriptionResult`, `DiarizationResult` are immutable result containers
- **Per-module loggers**: `logger = logging.getLogger(__name__)` at module level; configure via `logging_config.py`
- **All defaults in `constants.py`**: Do not hardcode values that are already defined there
- **Environment variables for secrets**: `HF_TOKEN`, `ASSEMBLY_AI_KEY` - never in code
- **File I/O**: Always `encoding="utf-8"` and `ensure_ascii=False` for JSON
