import io
from typing import List

from wx41.context import PipelineContext


class ProgressConsole:
    def __init__(self, output_stream: io.IOBase):
        self._console = _ConsoleWrapper(output_stream)

    def on_pipeline_start(self, step_names: List[str], ctx: PipelineContext) -> None:
        self._console.print(f"Pipeline: {step_names}")

    def on_step_start(self, name: str, ctx: PipelineContext) -> None:
        self._console.print(f"  [{name}] starting")

    def on_step_end(self, name: str, ctx: PipelineContext) -> None:
        self._console.print(f"  [{name}] done")

    def on_pipeline_end(self, ctx: PipelineContext) -> None:
        self._console.print("Pipeline done")


class _ConsoleWrapper:
    def __init__(self, stream: io.IOBase):
        self._stream = stream

    def print(self, message: str) -> None:
        self._stream.write(message + "\n")
