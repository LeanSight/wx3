import io
import pytest
from wx41.ui.progress import ProgressConsole


def test_progress_console_shows_step_name():
    out = io.StringIO()
    console = ProgressConsole(out)
    console.on_pipeline_start(["transcribe"], None)
    console.on_step_start("transcribe", None)
    console.on_step_end("transcribe", None)
    console.on_pipeline_end(None)
    
    output = out.getvalue()
    assert "transcribe" in output.lower(), (
        f"Expected 'transcribe' in output, but got: {output!r}"
    )
