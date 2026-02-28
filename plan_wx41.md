# Plan ATDD/TDD: Implementacion de wx41

## Principios de trabajo

**ATDD**: Cada step se especifica primero como acceptance criteria conductuales.
Los tests codifican ese contrato antes de que exista implementacion.

**TDD** por step:
1. RED: escribir `wx41/tests/test_{step}_step.py`. Los tests fallan porque el modulo no existe.
2. GREEN: escribir `wx41/steps/{step}.py` con la implementacion minima que pasa los tests.
3. REFACTOR: aplicar patrones de wx41.md sin romper tests.

**Regla de tests**: Solo archivos `test_{step}_step.py`. No se escriben tests para
`pipeline.py`, `cli.py`, ni `MediaOrchestrator`. `step_common.py` se prueba
implicitamente a traves de los tests de steps.

---

## Estructura de directorios a crear

```
wx41/
  __init__.py
  context.py          PipelineContext (sin cache_hit/cache; con media_type)
                      PipelineConfig (compress_ratio, transcribe_backend, force,
                                     skip_normalize, skip_enhance)
                      INTERMEDIATE_BY_STEP
  step_common.py      @timer, atomic_output, temp_files, run_compression,
                      PipelineState
  pipeline.py         NamedStep, Pipeline, PipelineObserver, StepDecision,
                      MediaType, build_audio_pipeline, build_video_pipeline,
                      MediaOrchestrator, detect_media_type, make_initial_ctx
  cli.py              RichPipelineObserver, _build_dry_run_table,
                      _build_summary_table, app (Typer), main()
  steps/
    __init__.py
    normalize.py
    enhance.py
    transcribe.py
    srt.py
    black_video.py     NUEVO (extraido de wx4/steps/video.py, sin compresion)
    compress.py
  tests/
    __init__.py
    conftest.py        fixture _ctx(tmp_path, **kwargs) compartido
    test_normalize_step.py
    test_enhance_step.py
    test_transcribe_step.py
    test_srt_step.py
    test_black_video_step.py
    test_compress_step.py
```

**Eliminado vs wx4**: `cache_check_step` y `cache_save_step` no existen en wx41.
El mecanismo `PipelineState` en `step_common.py` reemplaza toda su funcionalidad.
No hay `test_cache_check_step.py` ni `test_cache_save_step.py`.

**Importaciones de nivel inferior**: Los steps de wx41 importan de `wx4.*` para
todos los modulos de nivel inferior sin cambios (audio_extract, audio_normalize,
audio_enhance, audio_encode, video_black, compress_video, format_srt,
transcribe_wx3). La excepcion es `transcribe_aai`, que se actualiza para aceptar
`progress_callback` (ver Fase 1, Step 3).

---

## Fase 0: Infraestructura base (sin ciclo TDD, no son steps)

### 0.1 wx41/context.py

Base: `wx4/context.py`. Cambios:

**PipelineConfig** nueva:
```python
@dataclass(frozen=True)
class PipelineConfig:
    compress_ratio: Optional[float] = None
    transcribe_backend: str = "assemblyai"
    force: bool = False
    skip_normalize: bool = False
    skip_enhance: bool = False
```

**PipelineContext** cambios:
- ELIMINAR: `cache_hit: bool`, `cache: Dict[str, Any]`
- AGREGAR: `media_type: str = "audio"`
- CONSERVAR: `force: bool`, `skip_normalize: bool`, `skip_enhance: bool`
  (copiados desde config en `make_initial_ctx`)

**INTERMEDIATE_BY_STEP**: agregar clave `"black_video"` con sufijo `"_timestamps.mp4"`.
La clave existente `"video"` puede mantenerse como alias o eliminarse.

### 0.2 wx41/step_common.py

```python
import dataclasses
import functools
import json
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Optional

from wx41.context import PipelineContext


def timer(step_name: str):
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(ctx: PipelineContext) -> PipelineContext:
            t0 = time.perf_counter()
            result = fn(ctx)
            elapsed = time.perf_counter() - t0
            return dataclasses.replace(result, timings={**result.timings, step_name: elapsed})
        return wrapper
    return decorator


@contextmanager
def atomic_output(target: Path):
    with tempfile.NamedTemporaryFile(
        delete=False, dir=target.parent, suffix=target.suffix + ".tmp"
    ) as tmp_file:
        tmp_path = Path(tmp_file.name)
    try:
        yield tmp_path
        tmp_path.rename(target)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink()
        raise


@contextmanager
def temp_files(*paths: Path):
    try:
        yield paths
    finally:
        for p in paths:
            if p is not None and p.exists():
                p.unlink()


def run_compression(src_video, audio_source, out, ratio, progress_callback=None):
    from wx4.compress_video import (
        LufsInfo, calculate_video_bitrate, compress_video,
        detect_best_encoder, measure_audio_lufs, probe_video,
    )
    info = probe_video(src_video)
    lufs = (
        LufsInfo.from_measured(measure_audio_lufs(audio_source))
        if info.has_audio
        else LufsInfo.noop()
    )
    encoder = detect_best_encoder(force=None)
    bitrate = calculate_video_bitrate(info, ratio)
    compress_video(info, lufs, encoder, bitrate, out, progress_callback=progress_callback)


@dataclass(frozen=True)
class PipelineState:
    completed_steps: tuple[str, ...] = ()
    user_skipped_steps: tuple[str, ...] = ()

    @classmethod
    def empty(cls) -> "PipelineState":
        return cls()

    @classmethod
    def load(cls, path: Path) -> "PipelineState":
        if not path.exists():
            return cls()
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            completed_steps=tuple(data.get("completed_steps", [])),
            user_skipped_steps=tuple(data.get("user_skipped_steps", [])),
        )

    def save(self, path: Path) -> None:
        payload = {
            "completed_steps": list(self.completed_steps),
            "user_skipped_steps": list(self.user_skipped_steps),
        }
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def was_done(self, step_name: str) -> bool:
        return step_name in self.completed_steps or step_name in self.user_skipped_steps

    def mark_complete(self, name: str) -> "PipelineState":
        return dataclasses.replace(self, completed_steps=(*self.completed_steps, name))

    def mark_user_skipped(self, name: str) -> "PipelineState":
        return dataclasses.replace(
            self, user_skipped_steps=(*self.user_skipped_steps, name)
        )
```

### 0.3 wx41/__init__.py y wx41/steps/__init__.py

Archivos vacios. `wx41/steps/__init__.py` se completa al final con exports.

---

## Fase 1: Steps con ciclo RED-GREEN-REFACTOR

### Fixture compartido (conftest.py) - crear antes de los tests

```python
from dataclasses import field
from pathlib import Path
import pytest
from wx41.context import PipelineContext

def _ctx(tmp_path: Path, **kwargs) -> PipelineContext:
    src = tmp_path / "audio.mp3"
    if not src.exists():
        src.write_bytes(b"fake audio")
    return PipelineContext(src=src, **kwargs)
```

Todos los test files importan `_ctx` de `conftest.py`.

---

### Step 1 - normalize

**Acceptance criteria (ATDD)**:
- Dado audio fuente: ejecuta extract -> normalize -> encode en secuencia
- Dado output_m4a=True: produce archivo .m4a en `result.normalized`
- Dado output_m4a=False: usa rename directo (sin to_aac)
- Dado extract_to_wav falla: lanza RuntimeError
- Dado to_aac falla: lanza RuntimeError Y tmp_raw/tmp_norm eliminados
- Dado step_progress: se llama con (0,3), (1,3), (3,3) en ese orden
- Siempre: "normalize" en result.timings
- NO existe logica interna de skip (el pipeline gestiona esto via PipelineState)

**Tests eliminados vs wx4** (comportamiento ya no es del step):
- `test_skips_when_cache_hit`
- `test_skips_on_cache_hit`
- `test_returns_early_if_output_exists`

**RED**: `wx41/tests/test_normalize_step.py`

```
TestNormalizeStepHappyPath
  test_calls_extract_normalize_encode_in_order
  test_result_normalized_is_set
  test_timing_recorded

TestNormalizeStepEncodeWav
  test_output_m4a_false_uses_rename_not_to_aac
  test_output_m4a_true_calls_to_aac

TestNormalizeStepAtomicity
  test_tmp_raw_deleted_on_success
  test_tmp_norm_deleted_on_success
  test_tmp_raw_deleted_on_to_aac_failure
  test_raises_on_extract_failure

TestNormalizeStepProgress
  test_step_progress_called_with_0_3_before_extract
  test_step_progress_called_with_1_3_after_extract
  test_step_progress_called_with_3_3_after_encode
```

Patron de patch: `patch("wx41.steps.normalize.extract_to_wav", ...)`

**GREEN**: `wx41/steps/normalize.py`
- Importa de `wx4.audio_extract`, `wx4.audio_normalize`, `wx4.audio_encode`
- Aplica `@timer("normalize")` de `wx41.step_common`
- Usa `temp_files(tmp_raw, tmp_norm)` en lugar de `try/finally` manual
- Usa `atomic_output(out)` para escritura atomica de .m4a
- Elimina `if ctx.cache_hit or out.exists(): return ...`
- Elimina `t0 = time.time()` y el `timings=...` manual

---

### Step 2 - enhance

**Acceptance criteria (ATDD)**:
- Dado normalized!=None: usa normalized como audio_input
- Dado normalized=None: usa src como audio_input
- Dado apply_clearvoice exitoso + output_m4a=True: produce .m4a en `result.enhanced`
- Dado to_aac falla: lanza RuntimeError Y tmp_enh eliminado
- Dado step_progress: se pasa como progress_callback a apply_clearvoice
- Siempre: "enhance" en result.timings
- NO existe logica interna de skip

**Tests eliminados vs wx4**:
- `test_returns_cached_path_on_hit`

**RED**: `wx41/tests/test_enhance_step.py`

```
TestEnhanceStepHappyPath
  test_uses_normalized_as_audio_input_when_set
  test_uses_src_as_audio_input_when_normalized_is_none
  test_result_enhanced_is_set
  test_timing_recorded

TestEnhanceStepAtomicity
  test_tmp_enh_deleted_on_success
  test_tmp_enh_deleted_on_to_aac_failure
  test_raises_on_to_aac_failure

TestEnhanceStepProgress
  test_step_progress_forwarded_to_apply_clearvoice
```

Patron de patch: `patch("wx41.steps.enhance.apply_clearvoice", ...)`,
`patch("wx41.steps.enhance._get_model", ...)`

**GREEN**: `wx41/steps/enhance.py`
- Importa de `wx4.audio_enhance`, `wx4.audio_encode`, `wx4.model_cache`
- Aplica `@timer("enhance")`
- Usa `atomic_output(out)` para .m4a
- Usa `temp_files(tmp_enh)` en lugar de `try/finally` manual
- Elimina `if ctx.cache_hit and ctx.enhanced is not None: return ...`

---

### Step 3 - transcribe

**Acceptance criteria (ATDD)**:
- Dado enhanced!=None: usa enhanced como audio de entrada
- Dado enhanced=None: usa src
- Dado backend="assemblyai": llama transcribe_assemblyai con progress_callback
- Dado backend="whisper": llama transcribe_with_whisper con hf_token, device, whisper_model
- Dado backend desconocido: lanza RuntimeError con nombre del backend
- Siempre: result.transcript_txt y result.transcript_json seteados

**Cambio vs wx4**: `@timer("transcribe")`, pasa `ctx.step_progress` como
`progress_callback` a `transcribe_assemblyai`. `transcribe_aai.py` en wx4 se
actualiza para aceptar el parametro (ver nota al final de esta seccion).

**RED**: `wx41/tests/test_transcribe_step.py`

```
TestTranscribeAudioSelection
  test_uses_enhanced_when_set
  test_uses_src_when_enhanced_is_none

TestTranscribeBackendBranching
  test_calls_assemblyai_for_default_backend
  test_calls_whisper_for_whisper_backend
  test_raises_for_unknown_backend
  test_passes_progress_callback_to_assemblyai

TestTranscribeOutputPaths
  test_sets_transcript_txt
  test_sets_transcript_json
  test_timing_recorded
```

**GREEN**: `wx41/steps/transcribe.py`
- Importa de `wx4.transcribe_aai`, `wx4.transcribe_wx3`
- Aplica `@timer("transcribe")`
- Pasa `progress_callback=ctx.step_progress` a `transcribe_assemblyai`

**Nota sobre transcribe_aai.py**: Actualizar `wx4/transcribe_aai.py` para aceptar
`progress_callback: Optional[Callable[[int, int], None]] = None` y usar
`Transcriber.submit()` + polling manual (ver wx41.md seccion 3.9). Este cambio
es backwards-compatible (parametro opcional). Los tests del step mockean
`transcribe_assemblyai` completo, por lo que no requieren cambios en tests de step.

---

### Step 4 - srt

**Acceptance criteria (ATDD)**:
- Dado transcript_json=None: lanza RuntimeError
- Dado transcript_json existe: lee JSON, llama words_to_srt, escribe .srt
- Siempre: result.srt != None, suffix == ".srt"

**Cambio vs wx4**: solo `@timer("srt")`.

**RED**: `wx41/tests/test_srt_step.py`

```
TestSrtStepHappyPath
  test_reads_json_and_calls_words_to_srt
  test_result_srt_has_srt_suffix
  test_result_srt_is_set
  test_timing_recorded

TestSrtStepGuards
  test_raises_when_transcript_json_is_none
```

**GREEN**: `wx41/steps/srt.py`
- Importa de `wx4.format_srt`
- Aplica `@timer("srt")`

---

### Step 5 - black_video (NUEVO)

**Acceptance criteria (ATDD)**:
- Dado enhanced!=None: usa enhanced como audio de entrada
- Dado enhanced=None y normalized!=None: usa normalized
- Dado enhanced=None y normalized=None: usa src
- Dado audio_to_black_video retorna False: lanza RuntimeError con nombre del archivo
- Dado audio_to_black_video retorna True: result.video_out != None, suffix == ".mp4"
- NO existe logica de compresion interna (compress_ratio en ctx no se usa aqui)
- Siempre: "black_video" en result.timings

**Tests que NO se migran de TestVideoStep** (comportamiento eliminado):
- `test_video_step_with_compress_uses_enhanced_audio`
- `test_video_step_compression_ratio_applied`
- `test_video_step_no_compress_when_ratio_none`

**RED**: `wx41/tests/test_black_video_step.py`

```
TestBlackVideoStepAudioSelection
  test_uses_enhanced_when_set
  test_uses_normalized_when_enhanced_is_none
  test_uses_src_when_both_are_none

TestBlackVideoStepHappyPath
  test_video_out_is_set_on_success
  test_video_out_has_mp4_suffix
  test_timing_recorded

TestBlackVideoStepFailure
  test_raises_when_audio_to_black_video_returns_false
  test_error_message_contains_filename

TestBlackVideoStepNoCompress
  test_compress_ratio_set_does_not_trigger_compression
```

Patron de patch: `patch("wx41.steps.black_video.audio_to_black_video", ...)`

**GREEN**: `wx41/steps/black_video.py`

```python
import dataclasses
from wx41.context import INTERMEDIATE_BY_STEP, PipelineContext
from wx41.step_common import timer
from wx4.video_black import audio_to_black_video


@timer("black_video")
def black_video_step(ctx: PipelineContext) -> PipelineContext:
    audio = ctx.enhanced or ctx.normalized or ctx.src
    out = audio.parent / f"{audio.stem}{INTERMEDIATE_BY_STEP['black_video']}"
    if not audio_to_black_video(audio, out):
        raise RuntimeError(f"audio_to_black_video failed for {audio.name}")
    return dataclasses.replace(ctx, video_out=out)
```

---

### Step 6 - compress

**Acceptance criteria (ATDD)**:
- Dado media_type="video": usa ctx.src como fuente de video a comprimir
- Dado media_type="audio": usa ctx.video_out como fuente (video negro generado)
- Dado enhanced!=None: usa enhanced como fuente de audio para LUFS
- Dado enhanced=None: usa la fuente de video como fuente de audio
- Dado probe_video falla: lanza RuntimeError (NO silencioso; el pipeline solo
  incluye compress cuando aplica al tipo de medio)
- Dado step_progress: se pasa como progress_callback a run_compression
- Siempre: result.video_compressed seteado, "compress" en result.timings

**Cambios vs wx4**:
- Agregar logica de seleccion: `src = ctx.video_out if ctx.media_type == "audio" else ctx.src`
- Eliminar `try/except RuntimeError: return ctx` (ya no falla silenciosamente)
- Aplicar `@timer("compress")`
- Usar `run_compression` de `step_common.py`

**Tests que NO se migran** (comportamiento eliminado):
- `test_skips_silently_when_source_has_no_video_stream`
- `test_timing_recorded_on_audio_only_skip`

**RED**: `wx41/tests/test_compress_step.py`

```
TestCompressStepVideoInput
  test_uses_ctx_src_as_video_source_when_media_type_is_video
  test_uses_enhanced_audio_for_lufs_when_available

TestCompressStepAudioInput
  test_uses_ctx_video_out_as_video_source_when_media_type_is_audio
  test_raises_when_video_out_is_none_and_media_type_is_audio

TestCompressStepProbeFailure
  test_raises_on_probe_failure_without_silent_skip

TestCompressStepProgress
  test_step_progress_forwarded_to_run_compression

TestCompressStepOutput
  test_result_video_compressed_is_set
  test_timing_recorded
```

Patron de patch: `patch("wx41.steps.compress.run_compression", ...)`,
`patch("wx41.steps.compress.probe_video", ...)`

**GREEN**: `wx41/steps/compress.py`
- Importa `run_compression` de `wx41.step_common`
- Importa `probe_video` de `wx4.compress_video` (solo para validacion previa)
- Aplica `@timer("compress")`
- Implementa seleccion de fuente via `ctx.media_type`
- Elimina el `try/except RuntimeError` silencioso

---

## Fase 2: Pipeline, CLI, y cierre (sin tests)

### 2.1 wx41/pipeline.py

Implementar segun wx41.md secciones 5.1-5.6:
- `MediaType` (clase con constantes `AUDIO = "audio"`, `VIDEO = "video"`)
- `SkipReason = Literal["already_done", "user_skip", "not_done", "always_runs"]`
- `StepDecision` (dataclass frozen): `name, would_run, output_path, reason`
- `NamedStep` (dataclass): `name, fn, output_fn=None, skip_fn=None, ctx_setter=None`
- `PipelineObserver` (Protocol, @runtime_checkable)
- `Pipeline.run(ctx)`: usa `PipelineState` (ver 5.5)
- `Pipeline.dry_run(ctx)`: ignora `ctx.force` (ver 5.6)
- `build_audio_pipeline(config, observers) -> Pipeline`
- `build_video_pipeline(config, observers) -> Pipeline`
- `_TRANSCRIBE`, `_SRT` como instancias `NamedStep` compartidas
- `detect_media_type(src) -> str`: extension primero, ffprobe fallback
- `make_initial_ctx(src, config, media_type) -> PipelineContext`
- `_detect_intermediate_files(ctx) -> PipelineContext` (pura, para dry_run)
- `MediaOrchestrator`: `run(src)`, `dry_run(src)`, `_build_pipeline(media_type)`

### 2.2 wx41/cli.py

Implementar segun wx41.md seccion 6:
- `app = typer.Typer()`
- `RichPipelineObserver` (implementa `PipelineObserver`, tiene `reset()`)
- `_build_dry_run_table(src, media_type, decisions) -> Table`
- `_build_summary_table(ctx, elapsed) -> Table`
- `_expand_paths(paths) -> list[Path]` (expande directorios a archivos)
- `main()` con `@app.command()`: Typer + signal handling + loop multi-archivo
- `if __name__ == "__main__": app()`

Flags de Typer:
- `paths: list[Path]` - argumentos posicionales (uno o mas)
- `--compress FLOAT` - ratio de compresion (optional)
- `--backend TEXT` - assemblyai o whisper (default: assemblyai)
- `--force` - ignorar estado previo
- `--skip-normalize` - saltar step normalize
- `--skip-enhance` - saltar step enhance
- `--dry-run` - mostrar plan sin ejecutar

### 2.3 wx41/steps/__init__.py (completar)

```python
from wx41.steps.normalize import normalize_step
from wx41.steps.enhance import enhance_step
from wx41.steps.transcribe import transcribe_step
from wx41.steps.srt import srt_step
from wx41.steps.black_video import black_video_step
from wx41.steps.compress import compress_step
```

---

## Resumen de tests a crear

| Archivo | Clases de test | Comportamientos eliminados vs wx4 |
|---|---|---|
| test_normalize_step.py | HappyPath, EncodeWav, Atomicity, Progress | tests de skip por cache_hit |
| test_enhance_step.py | HappyPath, Atomicity, Progress | test de cache_hit skip |
| test_transcribe_step.py | AudioSelection, BackendBranching, OutputPaths | ninguno |
| test_srt_step.py | HappyPath, Guards | ninguno |
| test_black_video_step.py | AudioSelection, HappyPath, Failure, NoCompress | 3 tests de compresion interna |
| test_compress_step.py | VideoInput, AudioInput, ProbeFailure, Progress, Output | 2 tests de fallo silencioso |

**Eliminados vs plan original**: `test_cache_check_step.py` y `test_cache_save_step.py`
no se crean porque `cache_check_step` y `cache_save_step` no existen en wx41.

---

## Orden de implementacion recomendado

La secuencia respeta dependencias y va de lo mas simple a lo mas complejo:

```
Fase 0:  context.py, step_common.py, __init__.py
Step 1:  test_normalize_step.py -> normalize.py
Step 2:  test_enhance_step.py -> enhance.py
Step 3:  test_transcribe_step.py -> transcribe.py
         (+ actualizar wx4/transcribe_aai.py con progress_callback)
Step 4:  test_srt_step.py -> srt.py
Step 5:  test_black_video_step.py -> black_video.py
Step 6:  test_compress_step.py -> compress.py
Fase 2:  pipeline.py, cli.py, steps/__init__.py
```

---

## Verificacion

```bash
cd /home/user/wx3
pytest wx41/tests/ -v                          # todos los tests de steps
pytest wx41/tests/test_normalize_step.py -v    # un step especifico
pytest wx41/tests/ -v --tb=short               # con tracebacks cortos
```

Los tests de wx4 existentes no se tocan ni se eliminan.
