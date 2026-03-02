import json
import signal
from pathlib import Path
from typing import Dict, Optional

from wx41.context import PipelineContext


class InterruptHandler:
    def __init__(self, state_path: Path):
        self._state_path = state_path
        self._ctx: Optional[PipelineContext] = None
        self._original: Optional[signal.Handler] = None

    def install(self, ctx: PipelineContext):
        self._ctx = ctx
        self._original = signal.signal(signal.SIGINT, self._handle)

    def uninstall(self):
        if self._original is not None:
            signal.signal(signal.SIGINT, self._original)

    def update_ctx(self, ctx: PipelineContext):
        self._ctx = ctx

    def _handle(self, signum, frame):
        if self._ctx and self._state_path:
            state = {
                "src": str(self._ctx.src),
                "outputs": {k: str(v) for k, v in self._ctx.outputs.items()},
                "timings": self._ctx.timings,
            }
            self._state_path.write_text(
                json.dumps(state, ensure_ascii=False, indent=2), 
                encoding="utf-8"
            )
        raise KeyboardInterrupt
