# Plan: wx4 - ATDD + TDD Strict, One-Piece Flow

## Protocolo: RED -> GREEN -> REFACTOR por pieza

Para cada pieza:
1. Escribir SOLO el test file (pytest confirma RED)
2. Escribir implementacion minima para que pase (pytest confirma GREEN)
3. Refactorizar si hay oportunidad clara (pytest confirma GREEN)
4. Solo entonces avanzar a la siguiente pieza

---

## Estado de avance (v1 - pipeline base)

| # | Pieza                  | Test file                    | Impl file                    | Estado   |
|---|------------------------|------------------------------|------------------------------|----------|
| 0 | ATDD acceptance        | tests/test_acceptance.py     | (todos los modulos)          | GREEN    |
| 1 | conftest               | tests/conftest.py            | (fixtures)                   | DONE     |
| 2 | context                | tests/test_context.py        | context.py                   | GREEN    |
| 3 | speakers               | tests/test_speakers.py       | speakers.py                  | GREEN    |
| 4 | cache_io               | tests/test_cache_io.py       | cache_io.py                  | GREEN    |
| 5 | grouping               | tests/test_grouping.py       | common/grouping.py           | GREEN    |
| 6 | format_convert         | tests/test_format_convert.py | format_convert.py            | GREEN    |
| 7 | audio_extract          | tests/test_audio_extract.py  | audio_extract.py             | GREEN    |
| 8 | audio_normalize        | tests/test_audio_normalize.py| audio_normalize.py           | GREEN    |
| 9 | audio_enhance          | tests/test_audio_enhance.py  | audio_enhance.py             | GREEN    |
|10 | audio_encode           | tests/test_audio_encode.py   | audio_encode.py              | GREEN    |
|11 | video_black            | tests/test_video_black.py    | video_black.py               | GREEN    |
|12 | video_merge            | tests/test_video_merge.py    | video_merge.py               | GREEN    |
|13 | format_srt             | tests/test_format_srt.py     | format_srt.py                | GREEN    |
|14 | transcribe_aai         | tests/test_transcribe_aai.py | transcribe_aai.py            | GREEN    |
|15 | steps                  | tests/test_steps.py          | steps.py                     | GREEN    |
|16 | pipeline               | tests/test_pipeline.py       | pipeline.py                  | GREEN    |
|17 | cli                    | tests/test_cli.py            | cli.py                       | GREEN    |

---

## Estado de avance (v2 - TUI Progress + Resume)

| # | Pieza                             | Test file                    | Impl files                        | Estado   |
|---|-----------------------------------|------------------------------|-----------------------------------|----------|
| 1 | NamedStep + PipelineCallback + skip | test_pipeline.py           | pipeline.py                       | PENDIENTE |
| 2 | Atomicidad enhance_step + cleanup | test_steps.py                | steps.py                          | PENDIENTE |
| 3 | Atomicidad transcribe_aai         | test_transcribe_aai.py       | transcribe_aai.py                 | PENDIENTE |
| 4 | RichProgressCallback + CLI        | test_cli.py                  | cli.py                            | PENDIENTE |
| 5 | Fix video filename (player pairing) | test_steps.py, test_acceptance.py | steps.py                   | PENDIENTE |

---

## Diagnostico del codigo actual

### pipeline.py
- `build_steps()` retorna `List[Step]` (plain callables), no `List[NamedStep]`
- `Pipeline.__init__` no acepta `callbacks`
- `Pipeline.run()` no chequea `output_fn` para skip
- Tests en `TestBuildSteps` usan `cache_check_step in steps` - deben cambiar a
  `cache_check_step in [s.fn for s in steps]` despues de la migracion a NamedStep

### steps.py - enhance_step
- Crea 3 archivos tmp: `{stem}._tmp_raw.wav`, `{stem}._tmp_norm.wav`, `{stem}._tmp_enh.wav`
- NO los limpia si el proceso falla (finally block ausente)
- Escribe directamente a `out` sin patron tmp -> rename (no atomico)
- El archivo final puede quedar corrupto si muere a mitad del encode

### transcribe_aai.py
- `json_path.write_text(...)` escribe directamente al archivo final
- Si el proceso muere durante la escritura, queda un JSON corrupto
- La Pieza 1 de v2 detectaria ese JSON corrupto como "output exists -> skip"

### steps.py - video_step
- Output: `{audio.stem}_video.mp4`
- SRT output: `{audio.stem}_timestamps.srt`
- Stems distintos -> media players (VLC, MPC-HC) no los emparejan automaticamente
- Fix: cambiar a `{audio.stem}_timestamps.mp4`

### cli.py
- Solo tiene `console.print(f"Loading {_CV_MODEL}...")` sin barra de progreso
- `Pipeline(steps)` sin callbacks

---

## Plan v2 - Detalles de implementacion

### Pieza 1 - NamedStep + PipelineCallback + Pipeline con callbacks y skip

#### Tests nuevos en test_pipeline.py (RED primero)

```
TestNamedStep:
  test_callable_delegates_to_fn
  test_name_attribute
  test_output_path_returns_none_when_no_output_fn
  test_output_path_computed_from_fn

TestPipelineCallbacks:
  test_on_pipeline_start_called_with_step_names
  test_on_step_start_called_for_each_step
  test_on_step_end_called_for_each_step
  test_on_step_skipped_called_when_output_exists
  test_multiple_callbacks_all_called
  test_exception_in_step_does_not_call_on_step_end

TestPipelineResume:
  test_step_skipped_when_output_exists_and_no_force
  test_step_not_skipped_when_force_true
  test_step_not_skipped_when_output_does_not_exist
  test_ctx_not_modified_when_step_skipped
  test_step_without_output_fn_never_skipped
```

#### Tests existentes en TestBuildSteps que cambian

```python
# Antes:
assert cache_check_step in steps
# Despues:
step_fns = [s.fn for s in steps]
assert cache_check_step in step_fns
```

#### Implementacion en pipeline.py

```python
@dataclass
class NamedStep:
    name: str
    fn: Callable[[PipelineContext], PipelineContext]
    output_fn: Optional[Callable[[PipelineContext], Path]] = None

    def __call__(self, ctx):
        return self.fn(ctx)

    def output_path(self, ctx):
        return self.output_fn(ctx) if self.output_fn else None

class PipelineCallback(Protocol):
    def on_pipeline_start(self, step_names: List[str]) -> None: ...
    def on_step_start(self, name: str, ctx: PipelineContext) -> None: ...
    def on_step_end(self, name: str, ctx: PipelineContext) -> None: ...
    def on_step_skipped(self, name: str, ctx: PipelineContext) -> None: ...
    def on_pipeline_end(self, ctx: PipelineContext) -> None: ...
```

Output lambdas para build_steps():
```python
_ENHANCE_OUT    = lambda ctx: ctx.src.parent / f"{ctx.src.stem}_enhanced.m4a"
_TRANSCRIPT_JSON = lambda ctx: (ctx.enhanced or ctx.src).parent / f"{(ctx.enhanced or ctx.src).stem}_timestamps.json"
_SRT_OUT        = lambda ctx: (ctx.enhanced or ctx.src).parent / f"{(ctx.enhanced or ctx.src).stem}_timestamps.srt"
_VIDEO_OUT      = lambda ctx: (ctx.enhanced or ctx.src).parent / f"{(ctx.enhanced or ctx.src).stem}_timestamps.mp4"
```

Nota: cache_check y cache_save no declaran output_fn (su logica de skip es interna).

---

### Pieza 2 - Atomicidad en enhance_step + cleanup tmp files

#### Tests nuevos en test_steps.py (RED primero)

```
TestEnhanceStepAtomicity:
  test_tmp_files_removed_after_success
  test_final_output_written_atomically
  test_cleanup_runs_even_if_encode_fails
```

#### Implementacion en steps.py

```python
def enhance_step(ctx):
    ...
    try:
        if not extract_to_wav(ctx.src, tmp_raw):
            raise RuntimeError(...)
        normalize_lufs(tmp_raw, tmp_norm)
        apply_clearvoice(tmp_norm, tmp_enh, ctx.cv)
        tmp_out = out.with_suffix(".m4a.tmp")
        if ctx.output_m4a:
            if not to_aac(tmp_enh, tmp_out):
                raise RuntimeError(...)
            tmp_out.rename(out)   # atomico
        else:
            tmp_enh.rename(out)   # ya era atomico
    finally:
        for f in [tmp_raw, tmp_norm, tmp_enh]:
            if f.exists(): f.unlink()
    ...
```

---

### Pieza 3 - Atomicidad en transcribe_aai.py

#### Tests nuevos en test_transcribe_aai.py (RED primero)

```
TestTranscribeAssemblyaiAtomicity:
  test_writes_to_tmp_then_renames
  test_json_tmp_cleaned_up_on_success
```

#### Implementacion en transcribe_aai.py

```python
json_path = audio.parent / f"{audio.stem}_timestamps.json"
tmp_path = json_path.with_suffix(".json.tmp")
tmp_path.write_text(json.dumps(words, ...), encoding="utf-8")
tmp_path.rename(json_path)  # atomico
```

---

### Pieza 4 - RichProgressCallback + CLI con Progress

#### Tests nuevos en test_cli.py (RED primero)

```
TestCliProgress:
  test_progress_callback_passed_to_pipeline
  test_skip_enhance_includes_callback_too
```

Solo verificamos que el mecanismo de callbacks esta conectado, no el output visual.

#### Implementacion en cli.py

```python
class RichProgressCallback:
    def __init__(self, progress): ...
    def on_pipeline_start(self, step_names): ...
    def on_step_start(self, name, ctx): ...
    def on_step_end(self, name, ctx): ...
    def on_step_skipped(self, name, ctx):
        self._p.console.print(f"  [dim]{name}: already done, skipping[/dim]")
    def on_pipeline_end(self, ctx): ...

# En main():
with Progress(SpinnerColumn(), TextColumn("{task.description}"),
              TimeElapsedColumn(), BarColumn(), transient=True,
              console=console) as progress:
    cb = RichProgressCallback(progress)
    pipeline = Pipeline(steps, callbacks=[cb])
    ...
```

`transient=True`: la barra desaparece al terminar, solo queda la Summary Table.

---

### Pieza 5 - Fix video filename

```python
# steps.py video_step - antes:
out = audio.parent / f"{audio.stem}_video.mp4"
# despues:
out = audio.parent / f"{audio.stem}_timestamps.mp4"
```

Tests afectados:
- `test_steps.py::TestVideoStep::test_sets_video_out_on_ctx` (solo chequea `.mp4`, no cambia)
- `test_acceptance.py::test_video_step_produces_mp4` (solo chequea `.mp4`, no cambia)
- `test_pipeline.py` output lambdas `_VIDEO_OUT` usa `_timestamps.mp4` ya desde Pieza 1

---

## Verificacion final

```bash
pytest wx4/tests/test_pipeline.py -v        # Pieza 1
pytest wx4/tests/test_steps.py -v           # Piezas 2 y 5
pytest wx4/tests/test_transcribe_aai.py -v  # Pieza 3
pytest wx4/tests/test_cli.py -v             # Pieza 4
pytest wx4/tests/ -v                        # Suite completa: 164+ passed
```

Test manual de resume:
1. Correr el pipeline, interrumpirlo con Ctrl+C despues de que _enhanced.m4a exista
2. Volver a correr con el mismo archivo
3. Verificar que enhance no se vuelve a ejecutar (ClearVoice NO se carga de nuevo)
4. Verificar que si _timestamps.json ya existe, transcribe step se saltea

---

## Estructura de directorios

```
wx3/
  common/
    __init__.py
    types.py
    grouping.py

  wx4/
    __init__.py
    context.py
    speakers.py
    cache_io.py
    audio_extract.py
    audio_normalize.py
    audio_enhance.py
    audio_encode.py
    format_convert.py
    format_srt.py
    transcribe_aai.py
    video_black.py
    video_merge.py
    steps.py
    pipeline.py
    cli.py
    PLAN.md
    tui_research.md

    tests/
      __init__.py
      conftest.py
      test_acceptance.py
      test_context.py
      test_speakers.py
      test_cache_io.py
      test_grouping.py
      test_format_convert.py
      test_audio_extract.py
      test_audio_normalize.py
      test_audio_enhance.py
      test_audio_encode.py
      test_video_black.py
      test_video_merge.py
      test_format_srt.py
      test_transcribe_aai.py
      test_steps.py
      test_pipeline.py
      test_cli.py
```

---

## Grafo de dependencias

```
Nivel 0 (sin deps):  common/types.py, wx4/context.py
Nivel 1 (puras):     wx4/speakers.py, wx4/format_convert.py
Nivel 2 (IO local):  wx4/cache_io.py, common/grouping.py
Nivel 3 (ffmpeg):    wx4/audio_extract.py, audio_normalize.py,
                     audio_encode.py, video_black.py, video_merge.py
Nivel 4 (duck-type): wx4/audio_enhance.py
Nivel 5 (compuesta): wx4/format_srt.py
Nivel 6 (API ext):   wx4/transcribe_aai.py
Nivel 7 (orquesta):  wx4/steps.py
Nivel 8:             wx4/pipeline.py
Nivel 9:             wx4/cli.py
```
