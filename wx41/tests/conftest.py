from pathlib import Path

import pytest

from wx41.context import PipelineContext


def make_ctx(tmp_path: Path, **kwargs) -> PipelineContext:
    src = tmp_path / "audio.m4a"
    src.touch()
    return PipelineContext(src=src, **kwargs)
