# Fixes requeridos para que S1 pase GREEN

## Estado actual

`pytest wx41/tests/ -v` falla con ModuleNotFoundError en coleccion.
1 test pasa (test_pipeline.py), 2 archivos fallan antes de ejecutar.

---

## Fix 1 — Imports top-level de librerias opcionales (BLOQUEANTE)

### Problema

`wx41/transcribe_aai.py:6`:
```python
import assemblyai as aai  # falla si assemblyai no esta instalado
```

`wx41/transcribe_whisper.py:5-6`:
```python
import torch
from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline
```

Estos imports en el nivel del modulo rompen la coleccion de pytest cuando las
librerias no estan instaladas. Todos los tests que importan estos modulos fallan
con `ModuleNotFoundError` antes de ejecutar ni un solo test.

### Regla del proyecto

Toda libreria opcional (assemblyai, torch, transformers, clearvoice, pyannote)
se carga siempre de forma lazy. El proyecto ya tiene dos utilidades para esto:

**Para librerias simples** — patrón `lazy_load` de `lazy_loading.py`:
```python
from lazy_loading import lazy_load

def transcribe_assemblyai(...):
    aai = lazy_load("assemblyai", "")
    ...
```

**Para modelos pesados** — patron `_get_model` de `wx4/model_cache.py`:
```python
from wx4.model_cache import _get_model

def _load_whisper_pipe(model_id, torch_dtype, device):
    from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline
    import torch
    ...
    return pipe

def transcribe_whisper(...):
    import torch
    pipe = _get_model(model, lambda: _load_whisper_pipe(model, ...))
    ...
```

El patron de `wx4/steps/enhance.py` es el modelo a seguir:
```python
def _load_clearvoice():
    from clearvoice import ClearVoice
    return ClearVoice(task="speech_enhancement", model_names=[_CV_MODEL])

def enhance_step(ctx):
    cv = _get_model("MossFormer2", _load_clearvoice)
    ...
```

### Fix concreto

`wx41/transcribe_aai.py`: mover `import assemblyai as aai` dentro de
`transcribe_assemblyai()` usando `lazy_load`.

`wx41/transcribe_whisper.py`:
- Mover `import torch` y `from transformers import ...` dentro de la funcion
- Extraer la carga del modelo a `_load_whisper_pipeline(model_id)` privada
- Usar `_get_model(model_id, lambda: _load_whisper_pipeline(model_id))` para cachear

wx41 debe tener su propio `wx41/model_cache.py` portado de `wx4/model_cache.py`
(no importar directamente de wx4 para mantener independencia de paquetes).

---

## Fix 2 — Unit test usa fixture de audio real

### Problema

`wx41/tests/test_transcribe_step.py::test_transcribe_happy_path` usa el fixture
`audio_file` que requiere `wx41/tests/fixtures/sample_1m.m4a`. Este directorio
esta en `.gitignore` y no existe en el repo. El test llama `pytest.fail()` en
coleccion si el archivo no existe.

Sin embargo, el test es un unit test puro: monkeypatcha `transcribe_assemblyai`
y solo usa `audio_file` como `PipelineContext(src=audio_file)`. No lee el audio.

### Fix

Reemplazar el fixture `audio_file` por `tmp_path` con un archivo vacio:

```python
def test_transcribe_happy_path(self, tmp_path, monkeypatch):
    audio = tmp_path / "audio.m4a"
    audio.touch()
    ctx = PipelineContext(src=audio)
    ...
```

---

## Fix 3 — AT usa audio real con whisper real (CI unsafe)

### Problema

`wx41/tests/test_acceptance.py::test_produces_transcript_files_with_whisper`
usa el fixture `audio_file` (mismo problema que Fix 2) y ademas ejecuta
inferencia real de whisper.

CLAUDE.md: "There are no integration tests that require real audio files in CI."

### Fix

El AT verifica WIRING (orquestador -> pipeline -> step -> ctx.outputs), no
calidad de transcripcion. Usar `tmp_path` + Nullable de whisper via monkeypatch:

```python
def test_produces_transcript_files_with_whisper(self, tmp_path, monkeypatch):
    audio = tmp_path / "audio.m4a"
    audio.touch()
    config = PipelineConfig(settings={"transcribe": TranscribeConfig(backend="whisper")})
    transcribe_cfg = config.settings["transcribe"]

    def fake_whisper(src, **kw):
        txt = src.parent / f"{src.stem}_whisper.txt"
        jsn = src.parent / f"{src.stem}_whisper.json"
        txt.write_text("hello world", encoding="utf-8")
        jsn.write_text("[]", encoding="utf-8")
        return txt, jsn

    monkeypatch.setattr("wx41.steps.transcribe.transcribe_whisper", fake_whisper)

    ctx = MediaOrchestrator(config, []).run(audio)

    for key in transcribe_cfg.output_keys:
        assert key in ctx.outputs, f"{key} not in ctx.outputs: {ctx.outputs}"
        assert ctx.outputs[key].exists(), f"file not created: {ctx.outputs[key]}"
        content = ctx.outputs[key].read_text(encoding="utf-8")
        assert len(content) > 0, f"file is empty: {ctx.outputs[key]}"
```

---

## Archivos a modificar

| Archivo | Cambio |
|---------|--------|
| `wx41/transcribe_aai.py` | `import assemblyai` lazy via `lazy_load` dentro de la funcion |
| `wx41/transcribe_whisper.py` | Imports lazy + extraer `_load_whisper_pipeline` + usar `_get_model` |
| `wx41/model_cache.py` | Crear: port de `wx4/model_cache.py` para mantener independencia |
| `wx41/tests/test_transcribe_step.py` | Reemplazar `audio_file` por `tmp_path / "audio.m4a"` |
| `wx41/tests/test_acceptance.py` | Reemplazar `audio_file` por `tmp_path` + Nullable de whisper |

---

## Verificacion esperada

```
pytest wx41/tests/ -v

wx41/tests/test_acceptance.py::TestPipelineWalkingSkeleton::test_produces_transcript_files_with_whisper PASSED
wx41/tests/test_pipeline.py::TestPipelineGenericCore::test_automatic_output_registration PASSED
wx41/tests/test_transcribe_step.py::TestTranscribeStepModular::test_transcribe_happy_path PASSED

3 passed
```
