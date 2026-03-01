# fixs1.md — Correcciones pendientes post-S1

## Estado

3 problemas bloquean la ejecucion de tests en wx41. Ningun test del modulo
puede correr hasta que estos se corrijan.

---

## Problema 1 — Import top-level de assemblyai (BLOQUEANTE)

**Archivo:** `wx41/transcribe_aai.py`, linea 6
```python
import assemblyai as aai  # rompe coleccion si assemblyai no esta instalado
```

**Consecuencia:** `ModuleNotFoundError` al importar `wx41.transcribe_aai`.
Rompe coleccion de `test_acceptance.py` y `test_transcribe_step.py`.

**Regla:** toda libreria opcional se carga lazy. Ver patron en
`wx4/steps/enhance.py`: `_load_clearvoice()` importa `clearvoice` dentro
de la funcion, no en el modulo.

**Fix:** mover el import dentro de `transcribe_assemblyai()`:
```python
def transcribe_assemblyai(...):
    import assemblyai as aai
    ...
```

---

## Problema 2 — Imports top-level de torch y transformers (BLOQUEANTE)

**Archivo:** `wx41/transcribe_whisper.py`, lineas 5-7
```python
import torch
from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline
```

**Consecuencia:** igual que el anterior si torch/transformers no estan instalados.

**Regla:** misma que el Problema 1 para los imports de libreria.
Para la carga del modelo (pesada, varios GB), ademas se debe cachear usando
el patron `_get_model()` de `wx4/model_cache.py`.

**Fix — imports de libreria:** mover dentro de `transcribe_whisper()`:
```python
def transcribe_whisper(...):
    import torch
    from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline as hf_pipeline
    ...
```

**Fix — carga del modelo:** crear `wx41/model_cache.py` portando
`wx4/model_cache.py` sin cambios, luego usarlo:
```python
from wx41.model_cache import _get_model

def _load_whisper_model(model_id: str, device: str, torch_dtype):
    import torch
    from transformers import AutoModelForSpeechSeq2Seq
    return AutoModelForSpeechSeq2Seq.from_pretrained(
        model_id,
        torch_dtype=torch_dtype,
        low_cpu_mem_usage=True,
    ).to(device)

def transcribe_whisper(..., model: str = "openai/whisper-base"):
    import torch
    from transformers import AutoProcessor, pipeline as hf_pipeline

    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32

    loaded_model = _get_model(
        f"whisper:{model}",
        lambda: _load_whisper_model(model, device, torch_dtype),
    )
    processor = _get_model(
        f"whisper-processor:{model}",
        lambda: AutoProcessor.from_pretrained(model),
    )
    ...
```

---

## Problema 3 — Tests usan fixture de audio real

### 3a — test_transcribe_step.py usa audio_file innecesariamente

`test_transcribe_happy_path(self, audio_file, ...)` usa el fixture `audio_file`
que depende de `fixtures/sample_1m.m4a` (gitignored, no existe en CI).
El test solo necesita un `Path` para `PipelineContext(src=...)`, nunca lee el audio.

**Fix:** reemplazar `audio_file` por `tmp_path`:
```python
def test_transcribe_happy_path(self, tmp_path, monkeypatch):
    audio = tmp_path / "audio.m4a"
    audio.touch()
    ctx = PipelineContext(src=audio)
    ...
```

### 3b — conftest.py usa pytest.fail() en lugar de pytest.skip()

El AT en `test_acceptance.py` ES el test real de punta a cabo. Segun
`endtoendtests.md`, el ejemplo canonico usa `audio_file` con audio real:

```python
def test_produces_transcript_files(self, audio_file):
    ctx = MediaOrchestrator(config, []).run(audio_file)
    for key in transcribe_cfg.output_keys:
        assert ctx.outputs[key].exists()
```

El AT no debe mockearse. Debe correr con audio real cuando el fixture existe.

**El problema real no esta en el AT, sino en conftest.py:**
```python
# ACTUAL — mata la coleccion con pytest.fail():
if not fixture_path.exists():
    pytest.fail(f"Fixture no encontrado en {fixture_path}.")

# CORRECTO — salta el test si no hay fixture:
if not fixture_path.exists():
    pytest.skip(f"Fixture no disponible: {fixture_path}")
```

**Regla (CLAUDE.md):** "There are no integration tests that require real audio
files in CI." — se cumple porque el AT se SALTA en CI. No se elimina.

**Fix:** cambiar `pytest.fail()` por `pytest.skip()` en `conftest.py`:
```python
@pytest.fixture
def sample_audio_1m() -> Path:
    fixture_path = Path(__file__).parent / "fixtures" / "sample_1m.m4a"
    if not fixture_path.exists():
        pytest.skip(f"Fixture not available: {fixture_path}")
    return fixture_path
```

**Resultado:**
- CI (sin fixture): AT se salta → `pytest` pasa con 2 passed, 1 skipped
- Local (con fixture): AT corre real de punta a cabo con whisper real

---

## Archivos a crear/modificar

| Archivo | Accion |
|---------|--------|
| `wx41/model_cache.py` | Crear — port directo de `wx4/model_cache.py` |
| `wx41/transcribe_aai.py` | Mover `import assemblyai as aai` dentro de la funcion |
| `wx41/transcribe_whisper.py` | Mover imports dentro de la funcion; usar `_get_model` para el modelo |
| `wx41/tests/test_transcribe_step.py` | Reemplazar `audio_file` por `tmp_path` + `audio.touch()` |
| `wx41/tests/conftest.py` | Cambiar `pytest.fail()` por `pytest.skip()` en `sample_audio_1m` |

---

## Verificacion post-fix

```
pytest wx41/tests/ -v
```

Resultado esperado:
```
wx41/tests/test_acceptance.py::TestPipelineWalkingSkeleton::test_produces_transcript_files_with_whisper SKIPPED (fixture not available)
wx41/tests/test_pipeline.py::TestPipelineGenericCore::test_automatic_output_registration PASSED
wx41/tests/test_transcribe_step.py::TestTranscribeStepModular::test_transcribe_happy_path PASSED

2 passed, 1 skipped

# Con fixture local disponible (fixtures/sample_1m.m4a existe):
wx41/tests/test_acceptance.py::TestPipelineWalkingSkeleton::test_produces_transcript_files_with_whisper PASSED
wx41/tests/test_pipeline.py::TestPipelineGenericCore::test_automatic_output_registration PASSED
wx41/tests/test_transcribe_step.py::TestTranscribeStepModular::test_transcribe_happy_path PASSED

3 passed
```
