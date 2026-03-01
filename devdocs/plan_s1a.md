# Plan S1a: Fixes + Cerrar Brechas de UI, Dry Run, Resumability, Control+C

Fecha: 2026-03-01

Referencias:
- devdocs/standard-atdd-tdd.md
- devdocs/endtoendtests.md
- devdocs/arquitectura.md
- jamesshore.com/v2/projects/nullables/testing-without-mocks

---

## Reglas (endtoendtests.md)

1. **AT usa output_keys del config como fuente de verdad**: `transcribe_cfg.output_keys`, nunca hardcodear nombres de archivo
2. **Un AT por slice**: cover todo el wiring
3. **Ciclo ATDD**: AT RED → Unit RED → Prod GREEN → Commit + Push inmediato

---

## Estado Actual S1

| Objetivo | Estado | Slice |
|----------|--------|-------|
| Encadenado | OK | - |
| Declarativo/Modularidad | OK | - |
| Tests corren en CI | BLOQUEADO | Slice 0 |
| Visualizacion UI | Pendiente | Slice 2 |
| Resumability | Parcial | Slice 3 |
| Dry run | Pendiente | Slice 1 |
| Control+C graceful | Pendiente | Slice 4 |

---

## Nota sobre el AT del Walking Skeleton

`test_acceptance.py::test_produces_transcript_files_with_whisper` usa `audio_file`
(audio real) y se salta en CI via `pytest.skip` cuando el fixture no existe.
Esto sigue el patron de `endtoendtests.md`: el AT verifica comportamiento observable
con datos reales cuando estan disponibles. Los ATs de S1a usan `tmp_path` + Nullable
(fake_whisper via monkeypatch) porque validan wiring de features, no calidad de
transcripcion.

---

## Slice 0: Fixes bloqueantes (prerequisito)

3 problemas bloquean la coleccion de tests en CI.

### Fix 1 — Lazy import assemblyai

**Archivo:** `wx41/transcribe_aai.py`

```python
# ACTUAL (rompe coleccion si assemblyai no instalado):
import assemblyai as aai

# FIX (lazy import):
def transcribe_assemblyai(...):
    import assemblyai as aai
    ...
```

### Fix 2 — Lazy imports torch/transformers

**Archivo:** `wx41/transcribe_whisper.py`

```python
# ACTUAL (rompe coleccion si torch no instalado):
import torch
from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline

# FIX (lazy imports + model_cache):
def transcribe_whisper(..., model: str = "openai/whisper-base"):
    import torch
    from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline as hf_pipeline
    from wx41.model_cache import _get_model
    ...
```

Crear `wx41/model_cache.py` portando `wx4/model_cache.py` sin cambios.

### Fix 3a — test_transcribe_step.py usa audio_file innecesariamente

`test_transcribe_happy_path` solo necesita un Path para `PipelineContext(src=...)`.

```python
def test_transcribe_happy_path(self, tmp_path, monkeypatch):
    audio = tmp_path / "audio.m4a"
    audio.touch()
    ctx = PipelineContext(src=audio)
    ...
```

### Fix 3b — conftest.py usa pytest.fail en lugar de pytest.skip

```python
@pytest.fixture
def sample_audio_1m() -> Path:
    fixture_path = Path(__file__).parent / "fixtures" / "sample_1m.m4a"
    if not fixture_path.exists():
        pytest.skip(f"Fixture not available: {fixture_path}")
    return fixture_path
```

### Verificacion post-Slice 0

```
pytest wx41/tests/ -v
```

Sin fixture: `2 passed, 1 skipped`
Con fixture: `3 passed`

Commit + push.

---

## Slice 1: Dry Run

**Archivos:** `wx41/context.py`, `wx41/pipeline.py`, `wx41/tests/test_dry_run.py`

### AT (RED)

```python
# wx41/tests/test_dry_run.py
from pathlib import Path
import pytest
from wx41.pipeline import MediaOrchestrator
from wx41.context import PipelineConfig, PipelineContext
from wx41.steps.transcribe import TranscribeConfig

def test_dry_run_no_execution(tmp_path):
    audio = tmp_path / "test.m4a"
    audio.touch()
    config = PipelineConfig(settings={"transcribe": TranscribeConfig(backend="whisper")})
    transcribe_cfg = config.settings["transcribe"]

    orchestrator = MediaOrchestrator(config, [])
    ctx = orchestrator.run(audio, dry_run=True)

    for key in transcribe_cfg.output_keys:
        assert key not in ctx.outputs, f"{key} no debe estar en ctx.outputs en dry run"
    assert ctx.dry_run is True
```

### Produccion minima

`context.py`: agregar `dry_run: bool = False` a `PipelineContext`.

`pipeline.py`:
- `Pipeline.run(ctx, dry_run=False)`: si `dry_run=True`, notifica `on_pipeline_start`, retorna sin ejecutar steps
- `MediaOrchestrator.run(src, dry_run=False)`: propaga `dry_run` a `Pipeline.run`

Commit + push.

---

## Slice 2: Visualizacion UI con Rich

**Archivos:** `wx41/ui/__init__.py`, `wx41/ui/progress.py`, `wx41/tests/test_progress.py`, `wx41/tests/test_ui_visualization.py`

`PipelineObserver` ya existe en `pipeline.py`. `ProgressConsole` implementa ese protocol.

### Unit Test (RED)

```python
# wx41/tests/test_progress.py
import io
from wx41.ui.progress import ProgressConsole

def test_progress_console_shows_step_name():
    out = io.StringIO()
    console = ProgressConsole(out)
    console.on_pipeline_start(["transcribe"], None)
    console.on_step_start("transcribe", None)
    console.on_step_end("transcribe", None)
    console.on_pipeline_end(None)
    assert "transcribe" in out.getvalue()
```

### AT (RED)

```python
# wx41/tests/test_ui_visualization.py
import io
from wx41.pipeline import MediaOrchestrator
from wx41.context import PipelineConfig
from wx41.steps.transcribe import TranscribeConfig
from wx41.ui.progress import ProgressConsole

def test_ui_shows_step_name_during_run(tmp_path, monkeypatch):
    audio = tmp_path / "test.m4a"
    audio.touch()
    config = PipelineConfig(settings={"transcribe": TranscribeConfig(backend="whisper")})

    def fake_whisper(src, **kw):
        txt = src.parent / f"{src.stem}_whisper.txt"
        jsn = src.parent / f"{src.stem}_whisper.json"
        txt.write_text("ok", encoding="utf-8")
        jsn.write_text("[]", encoding="utf-8")
        return txt, jsn
    monkeypatch.setattr("wx41.steps.transcribe.transcribe_whisper", fake_whisper)

    out = io.StringIO()
    observer = ProgressConsole(out)
    orchestrator = MediaOrchestrator(config, [observer])
    orchestrator.run(audio)

    assert "transcribe" in out.getvalue()
```

### Produccion minima

```python
# wx41/ui/progress.py
import io
from rich.console import Console

class ProgressConsole:
    def __init__(self, output_stream: io.IOBase):
        self._console = Console(file=output_stream, highlight=False)

    def on_pipeline_start(self, step_names, ctx):
        self._console.print(f"Pipeline: {step_names}")

    def on_step_start(self, name, ctx):
        self._console.print(f"  [{name}] starting")

    def on_step_end(self, name, ctx):
        self._console.print(f"  [{name}] done")

    def on_pipeline_end(self, ctx):
        self._console.print("Pipeline done")
```

Commit + push.

---

## Slice 3: Resumability

**Archivos:** `wx41/pipeline.py`, `wx41/tests/test_resume.py`

### AT (RED)

```python
# wx41/tests/test_resume.py
from wx41.pipeline import MediaOrchestrator
from wx41.context import PipelineConfig
from wx41.steps.transcribe import TranscribeConfig

def test_resume_skips_existing_outputs(tmp_path, monkeypatch):
    audio = tmp_path / "test.m4a"
    audio.touch()
    config = PipelineConfig(settings={"transcribe": TranscribeConfig(backend="whisper")})
    transcribe_cfg = config.settings["transcribe"]

    call_count = {"n": 0}
    def fake_whisper(src, **kw):
        call_count["n"] += 1
        txt = src.parent / f"{src.stem}_whisper.txt"
        jsn = src.parent / f"{src.stem}_whisper.json"
        txt.write_text("original", encoding="utf-8")
        jsn.write_text("[]", encoding="utf-8")
        return txt, jsn
    monkeypatch.setattr("wx41.steps.transcribe.transcribe_whisper", fake_whisper)

    orchestrator = MediaOrchestrator(config, [])

    ctx1 = orchestrator.run(audio)
    assert call_count["n"] == 1
    for key in transcribe_cfg.output_keys:
        assert ctx1.outputs[key].exists()

    ctx2 = orchestrator.run(audio, resume=True)
    assert call_count["n"] == 1, "whisper no debe ejecutarse si outputs ya existen"
    for key in transcribe_cfg.output_keys:
        assert ctx2.outputs[key].read_text(encoding="utf-8") == "original"
```

### Produccion minima

`pipeline.py`:
- `Pipeline.run(ctx, resume=False)`: cuando `resume=True`, antes de cada step verifica si sus outputs existen en disco via `step.output_fn`. Si existen, salta el step y registra el path existente en `ctx.outputs`.
- `MediaOrchestrator.run(src, resume=False)`: propaga `resume`.

Commit + push.

---

## Slice 4: Control+C Graceful

**Archivos:** `wx41/ui/interrupt.py`, `wx41/context.py`, `wx41/pipeline.py`, `wx41/tests/test_interrupt.py`

### AT (RED)

```python
# wx41/tests/test_interrupt.py
import signal
import os
import json
from wx41.pipeline import MediaOrchestrator
from wx41.context import PipelineConfig
from wx41.steps.transcribe import TranscribeConfig

def test_ctrl_c_marks_interrupted_and_saves_state(tmp_path, monkeypatch):
    audio = tmp_path / "test.m4a"
    audio.touch()
    config = PipelineConfig(settings={"transcribe": TranscribeConfig(backend="whisper")})
    transcribe_cfg = config.settings["transcribe"]
    state_file = tmp_path / ".wx41_state.json"

    def fake_whisper(src, **kw):
        txt = src.parent / f"{src.stem}_whisper.txt"
        jsn = src.parent / f"{src.stem}_whisper.json"
        txt.write_text("partial", encoding="utf-8")
        jsn.write_text("[]", encoding="utf-8")
        os.kill(os.getpid(), signal.SIGINT)
        return txt, jsn
    monkeypatch.setattr("wx41.steps.transcribe.transcribe_whisper", fake_whisper)

    orchestrator = MediaOrchestrator(config, [], state_path=state_file)
    ctx = orchestrator.run(audio)

    assert ctx.interrupted is True
    assert state_file.exists()
    state = json.loads(state_file.read_text(encoding="utf-8"))
    for key in transcribe_cfg.output_keys:
        if key in ctx.outputs:
            assert key in state["outputs"], f"{key} no esta en state guardado"
            assert ctx.outputs[key].exists()
```

### Produccion minima

`context.py`: agregar `interrupted: bool = False` a `PipelineContext`.

`wx41/ui/interrupt.py`:
```python
import signal
import json
from pathlib import Path

class InterruptHandler:
    def __init__(self, state_path: Path):
        self._state_path = state_path
        self._ctx = None
        self._original = None

    def install(self):
        self._original = signal.signal(signal.SIGINT, self._handle)

    def uninstall(self):
        if self._original is not None:
            signal.signal(signal.SIGINT, self._original)

    def update_ctx(self, ctx):
        self._ctx = ctx

    def _handle(self, signum, frame):
        if self._ctx and self._state_path:
            state = {
                "src": str(self._ctx.src),
                "outputs": {k: str(v) for k, v in self._ctx.outputs.items()},
                "timings": self._ctx.timings,
            }
            self._state_path.write_text(
                json.dumps(state), encoding="utf-8"
            )
        raise KeyboardInterrupt
```

`pipeline.py` / `MediaOrchestrator`: cuando `state_path` no es None, instalar
`InterruptHandler` antes de `pipeline.run()`, capturar `KeyboardInterrupt`,
marcar `ctx.interrupted = True`, retornar ctx en lugar de propagar la excepcion.

Commit + push.

---

## Tabla de archivos

| Archivo | Slice | Accion |
|---------|-------|--------|
| `wx41/model_cache.py` | 0 | Crear (port de wx4/model_cache.py) |
| `wx41/transcribe_aai.py` | 0 | Lazy import assemblyai |
| `wx41/transcribe_whisper.py` | 0 | Lazy imports + usar model_cache |
| `wx41/tests/test_transcribe_step.py` | 0 | tmp_path en lugar de audio_file |
| `wx41/tests/conftest.py` | 0 | pytest.skip en lugar de pytest.fail |
| `wx41/context.py` | 1, 4 | Agregar dry_run, interrupted |
| `wx41/pipeline.py` | 1, 3, 4 | dry_run, resume, InterruptHandler |
| `wx41/ui/__init__.py` | 2 | Crear vacio |
| `wx41/ui/progress.py` | 2 | ProgressConsole |
| `wx41/ui/interrupt.py` | 4 | InterruptHandler |
| `wx41/tests/test_dry_run.py` | 1 | Crear |
| `wx41/tests/test_progress.py` | 2 | Crear |
| `wx41/tests/test_ui_visualization.py` | 2 | Crear |
| `wx41/tests/test_resume.py` | 3 | Crear |
| `wx41/tests/test_interrupt.py` | 4 | Crear |

---

## Verificacion final

```
pytest wx41/tests/ -v
```

Sin fixture local:
```
test_acceptance.py::...::test_produces_transcript_files_with_whisper SKIPPED
test_dry_run.py::test_dry_run_no_execution PASSED
test_interrupt.py::test_ctrl_c_marks_interrupted_and_saves_state PASSED
test_pipeline.py::...::test_automatic_output_registration PASSED
test_progress.py::test_progress_console_shows_step_name PASSED
test_resume.py::test_resume_skips_existing_outputs PASSED
test_transcribe_step.py::...::test_transcribe_happy_path PASSED
test_ui_visualization.py::test_ui_shows_step_name_during_run PASSED

7 passed, 1 skipped
```
