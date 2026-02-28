# plan_wx41.md - Implementacion ATDD/TDD

Fecha: 2026-02-28
Ref: wx41.md (arquitectura y diseno), devdocs/standard-atdd-tdd.md (metodologia)

---

## Contexto

wx41/ es la reescritura limpia de wx4/ que elimina deuda tecnica acumulada:
- Skip logic duplicado dentro de los steps (responsabilidad del Pipeline)
- Dependencias de cache_check/cache_save (reemplazadas por PipelineState)
- Step video bifuncional (black_video + compress en uno) -> separar
- Timing boilerplate repetido en los 6 steps -> @timer decorator
- Atomic write y temp cleanup repetidos -> step_common utilities
- transcribe_aai.py bloqueante sin progress_callback -> submit + polling

## Decisiones de diseno (ya tomadas)

1. **Estructura flat**: sin logic/, infrastructure/, application/ subdirs.
   Separacion A-Frame como disciplina de imports, no de directorios.
2. **words_to_srt pura**: eliminar parametro `output_file`. Funcion retorna
   solo `str`. srt_step escribe el archivo con `write_text` explicitamente.
3. **Nullables via monkeypatch**: pragmatico equivalente a `create_null()` para
   infraestructura basada en funciones. NO mockear step_common ni logic.
4. **State-Based assertions**: NUNCA `assert_called_with` ni `call_count`.
   Siempre verificar ctx fields y archivos en disco con mensajes f-string.
5. **compress_step sin silencio**: `except RuntimeError: return` eliminado.
   Pipeline garantiza que compress_step se llama solo en contexto valido.

---

## Re-diagnostico A-Frame (PASO 5 de standard-atdd-tdd.md)

Arbol de decision aplicado a cada modulo wx4:

```
Necesita I/O?
  NO  -> logic (funcion pura, cero I/O)
  SI  -> tiene reglas de negocio?
            NO  -> infrastructure (wrapper puro de I/O)
            SI  -> SEPARAR: regla->logic, I/O->infrastructure, coord->application
```

### Clasificacion completa

| Modulo wx4 | Capa wx41 | Accion |
|------------|-----------|--------|
| `format_convert.py` (ms_to_seconds, assemblyai_words_to_chunks, wx3_chunks_to_aai_words) | logic | Copiar sin cambios |
| `format_srt.py` (_format_timestamp, chunks_to_srt) | logic | Copiar sin cambios |
| `format_srt.py` (words_to_srt) | logic | MODIFICAR: eliminar output_file, retorna solo str |
| `speakers.py` (parse_speakers_map) | logic | Copiar sin cambios |
| `compress_video.py` (calculate_video_bitrate, LufsInfo, VideoInfo, EncoderInfo) | logic | Copiar sin cambios |
| `audio_extract.py` (extract_to_wav) | infrastructure | Copiar sin cambios |
| `audio_encode.py` (to_aac) | infrastructure | Copiar sin cambios |
| `audio_enhance.py` (apply_clearvoice) | infrastructure | Copiar sin cambios |
| `audio_normalize.py` (measure_lufs, normalize_lufs) | infrastructure | Copiar sin cambios |
| `video_black.py` (audio_to_black_video) | infrastructure | Copiar sin cambios |
| `video_merge.py` (merge_video_audio) | infrastructure | Copiar sin cambios |
| `compress_video.py` (probe_video, measure_audio_lufs, detect_best_encoder, compress_video) | infrastructure | Copiar sin cambios |
| `transcribe_aai.py` (transcribe_assemblyai) | infrastructure | MODIFICAR: submit + polling + progress_callback |
| `transcribe_wx3.py` (transcribe_with_whisper) | infrastructure | Copiar sin cambios |
| `model_cache.py` (_get_model) | infrastructure | Copiar sin cambios |
| `cache_io.py` | ELIMINADO | Reemplazado por PipelineState en step_common.py |
| `steps/normalize.py` | application | MODIFICAR: ver cambios abajo |
| `steps/enhance.py` | application | MODIFICAR: ver cambios abajo |
| `steps/transcribe.py` | application | MODIFICAR: @timer + progress_callback |
| `steps/srt.py` | application | MODIFICAR: @timer + write_text explicito |
| `steps/video.py` | SEPARAR | black_video_step (solo video) + compress ya existe |
| `steps/compress.py` | application | MODIFICAR: run_compression + media_type + no silencio |

### Violaciones A-Frame identificadas en wx4 (todas se corrigen en wx41)

1. `normalize_step` y `enhance_step`: skip logic dentro del step -> eliminar
2. `video_step`: doble responsabilidad -> separar en black_video_step
3. `compress_step`: silencia RuntimeError de probe_video -> raise siempre
4. `words_to_srt`: I/O + logica de negocio mezcladas -> separar (decision 2)

---

## Tecnica de test por capa (A-Frame PASO 6)

| Capa | Tecnica | Nullables |
|------|---------|-----------|
| logic | State-Based: input -> assert output directo | Nunca |
| infrastructure | Narrow Integration Test con sistema real | Nunca |
| application (steps) | Sociable Test con Nullable via monkeypatch | Solo para I/O externo |

**Referencia obligatoria**: ver `devdocs/nullable_vs_mocks.md` para la diferencia entre
Nullables (SI) y Mocks (NO), y por que `step_common` no se toca.

Regla universal de assert:
```python
assert ctx.normalized is not None, "normalize_step debe setear ctx.normalized"
assert ctx.normalized.exists(), f"archivo no creado: {ctx.normalized}"
assert ctx.normalized.name.endswith(INTERMEDIATE_BY_STEP["normalize"]), f"sufijo: {ctx.normalized.name}"
assert "normalize" in ctx.timings, f"timings actuales: {ctx.timings}"
assert ctx.timings["normalize"] >= 0, f"timing invalido: {ctx.timings['normalize']}"
```

---

## Estructura wx41/ (completa)

```
wx41/
  __init__.py

  # logic (cero I/O)
  format_convert.py   ms_to_seconds, assemblyai_words_to_chunks, wx3_chunks_to_aai_words
  format_srt.py       words_to_srt->str, chunks_to_srt, _format_timestamp   [MODIFICADO]
  speakers.py         parse_speakers_map

  # infrastructure (wrappers I/O)
  audio_extract.py    extract_to_wav
  audio_encode.py     to_aac
  audio_enhance.py    apply_clearvoice
  audio_normalize.py  normalize_lufs, measure_lufs
  video_black.py      audio_to_black_video
  video_merge.py      merge_video_audio
  compress_video.py   probe_video, compress_video, detect_best_encoder, measure_audio_lufs,
                      calculate_video_bitrate, LufsInfo, VideoInfo, EncoderInfo
  transcribe_aai.py   transcribe_assemblyai                                  [MODIFICADO]
  transcribe_wx3.py   transcribe_with_whisper
  model_cache.py      _get_model

  # application shared
  context.py          PipelineContext, PipelineConfig, INTERMEDIATE_BY_STEP  [MODIFICADO]
  step_common.py      @timer, atomic_output, temp_files, run_compression, PipelineState  [NUEVO]
  pipeline.py         NamedStep, Pipeline, PipelineObserver, StepDecision,
                      MediaType, build_audio_pipeline, build_video_pipeline,
                      MediaOrchestrator, detect_media_type, make_initial_ctx
  cli.py              app Typer, RichPipelineObserver, main

  steps/
    __init__.py
    normalize.py      [MODIFICADO: sin skip, sin output_m4a, @timer, atomic_output, temp_files]
    enhance.py        [MODIFICADO: sin skip, sin output_m4a, @timer, atomic_output, temp_files]
    transcribe.py     [MODIFICADO: @timer, progress_callback]
    srt.py            [MODIFICADO: @timer, write_text explicito]
    black_video.py    [NUEVO: extraido de wx4/steps/video.py]
    compress.py       [MODIFICADO: run_compression, media_type routing, raise en error]

  tests/
    __init__.py
    conftest.py
    test_normalize_step.py
    test_enhance_step.py
    test_transcribe_step.py
    test_srt_step.py
    test_black_video_step.py
    test_compress_step.py
```

---

## Fase 0: Archivos base (sin TDD, precondicion para steps)

**wx41/context.py** (copiar wx4/context.py + limpiar):
- Eliminar: cache_hit, cache, output_m4a
- Agregar: `media_type: str = "audio"`
- INTERMEDIATE_BY_STEP: sin cambios

**wx41/step_common.py** (crear nuevo):
- `@timer(step_name)`: decorator, time.perf_counter(), actualiza ctx.timings
- `atomic_output(target)`: contextmanager, tmpfile + rename atomico
- `temp_files(*paths)`: contextmanager, unlink en finally
- `run_compression(src_video, audio_source, out, ratio, progress_callback=None)`:
  encapsula probe_video + measure_audio_lufs + detect_best_encoder +
  calculate_video_bitrate + compress_video
- `PipelineState`: dataclass frozen, load(path)/save(path)/empty()/
  was_done(step)/mark_complete(step)/mark_user_skipped(step)

**wx41/format_srt.py** (copiar + modificar):
- `words_to_srt`: eliminar parametro `output_file`, retorna solo `str`

**wx41/transcribe_aai.py** (copiar + modificar):
- Agregar `progress_callback: Optional[Callable[[int, int], None]] = None`
- Reemplazar `.transcribe()` por `.submit()` + polling con time.sleep(3)

Resto de archivos (logic y infrastructure sin cambios): copiar directamente de wx4/.

---

## Fase 1: Steps (ATDD/TDD)

Metodologia por slice:
```
Slice 1 - Walking Skeleton:
  RED   -> escribir AT, falla porque el step no existe
  DIAG  -> mejorar assert msgs con f-strings
  GREEN -> implementar step + Nullables via monkeypatch
  REFACTOR -> si hay duplicacion
  COMMIT + PUSH

Slice 2+ - Errores y borde:
  RED   -> escribir test de error especifico
  DIAG  -> pytest.raises(RuntimeError, match="texto exacto")
  GREEN -> implementar rama de error
  COMMIT + PUSH
```

---

### Step 1: normalize_step

Fuente: `wx4/steps/normalize.py`

Slices:
1. (Walking Skeleton) `normalize_step(ctx)` -> `ctx.normalized` + archivo `_normalized.m4a`
2. `extract_to_wav` retorna `False` -> `RuntimeError("extract_to_wav failed for ...")`
3. `to_aac` retorna `False` -> `RuntimeError("to_aac failed for ...")`, tmp files limpios
4. `ctx.timings["normalize"]` presente y `>= 0`

Nullables:
- `wx41.audio_extract.extract_to_wav` -> `lambda src, dst: True`
- `wx41.audio_normalize.normalize_lufs` -> `lambda src, dst, **kw: None`
- `wx41.audio_encode.to_aac` -> `lambda src, dst, **kw: (dst.touch(), True)[1]`

Cambios desde wx4 (con referencias de linea):
- ELIMINAR L28-33: `if ctx.cache_hit or out.exists(): return ...`
- ELIMINAR L50-57: rama `if ctx.output_m4a else` (siempre to_aac)
- REEMPLAZAR: `t0 = time.time()` + manual timings -> `@timer("normalize")`
- REEMPLAZAR: `tmp_out = out.with_suffix(".m4a.tmp"); tmp_out.rename(out)` -> `atomic_output(out)`
- REEMPLAZAR: `try/finally: for f in [tmp_raw, tmp_norm]...` -> `temp_files(tmp_raw, tmp_norm)`

---

### Step 2: enhance_step

Fuente: `wx4/steps/enhance.py`

Slices:
1. (Walking Skeleton) `enhance_step(ctx con normalized)` -> `ctx.enhanced` + archivo `_enhanced.m4a`
2. `ctx.normalized is None` -> usa `ctx.src` como audio_input
3. `to_aac` retorna `False` -> `RuntimeError("to_aac failed for ...")`, tmp limpio
4. `ctx.timings["enhance"]` presente y `>= 0`

Nullables:
- `wx41.model_cache._get_model` -> `lambda *a, **kw: object()` (objeto dummy)
- `wx41.audio_enhance.apply_clearvoice` -> `lambda src, dst, cv, **kw: dst.touch()`
- `wx41.audio_encode.to_aac` -> `lambda src, dst, **kw: (dst.touch(), True)[1]`

Cambios desde wx4 (con referencias de linea):
- ELIMINAR L31-34: `if ctx.cache_hit and ctx.enhanced is not None: return ...`
- ELIMINAR L49-55: rama `if ctx.output_m4a else` (siempre to_aac)
- REEMPLAZAR: timing manual -> `@timer("enhance")`
- REEMPLAZAR: atomic write manual -> `atomic_output(out)`
- REEMPLAZAR: try/finally -> `temp_files(tmp_enh)`

---

### Step 3: transcribe_step

Fuente: `wx4/steps/transcribe.py`

Slices:
1. (Walking Skeleton) `transcribe_step(ctx, backend="assemblyai")` -> `ctx.transcript_json` + `ctx.transcript_txt`
2. `backend="whisper"` -> delega a `transcribe_with_whisper`, ctx con paths correctos
3. `backend` desconocido -> `RuntimeError("Unknown transcribe_backend: ...")`
4. `ctx.enhanced` presente -> usa enhanced como audio (no ctx.src)
5. `ctx.timings["transcribe"]` presente y `>= 0`

Nullables:
- `wx41.transcribe_aai.transcribe_assemblyai` -> `lambda audio, **kw: (tmp_txt, tmp_json)`
- `wx41.transcribe_wx3.transcribe_with_whisper` -> `lambda audio, **kw: (tmp_txt, tmp_json)`

Cambios desde wx4:
- REEMPLAZAR: timing manual -> `@timer("transcribe")`
- AGREGAR: `progress_callback=ctx.step_progress` en llamada a `transcribe_assemblyai`

---

### Step 4: srt_step

Fuente: `wx4/steps/srt.py`

Slices:
1. (Walking Skeleton) `srt_step(ctx con transcript_json)` -> `ctx.srt` + archivo `.srt` con contenido
2. `ctx.transcript_json is None` -> `RuntimeError("transcript_json is None - ...")`
3. `ctx.timings["srt"]` presente y `>= 0`

Nullables: NINGUNO. `words_to_srt` es logic pura. srt_step usa:
```python
srt_content = words_to_srt(words, speaker_names=ctx.speaker_names, mode=ctx.srt_mode)
srt_path.write_text(srt_content, encoding="utf-8")
```
El AT de Slice 1 usa JSON fixture real. Verifica `ctx.srt.exists()` y contenido no vacio.

Cambios desde wx4:
- REEMPLAZAR: timing manual -> `@timer("srt")`
- CAMBIAR: `words_to_srt(..., output_file=str(srt_path))` -> capturar str + `write_text`

---

### Step 5: black_video_step

Fuente: `wx4/steps/video.py` (solo la parte black_video, sin compress_ratio)

Slices:
1. (Walking Skeleton) `black_video_step(ctx con enhanced)` -> `ctx.video_out` + `_timestamps.mp4`
2. `ctx.enhanced is None`, `ctx.normalized` existe -> usa normalized
3. enhanced y normalized `None` -> usa `ctx.src`
4. `audio_to_black_video` retorna `False` -> `RuntimeError("audio_to_black_video failed for ...")`
5. `ctx.timings["black_video"]` presente y `>= 0`

Nullables:
- `wx41.video_black.audio_to_black_video` -> `lambda audio, out: (out.touch(), True)[1]`

Implementacion (step nuevo):
```python
@timer("black_video")
def black_video_step(ctx: PipelineContext) -> PipelineContext:
    audio = ctx.enhanced or ctx.normalized or ctx.src
    out = audio.parent / f"{audio.stem}{INTERMEDIATE_BY_STEP['video']}"
    if not audio_to_black_video(audio, out):
        raise RuntimeError(f"audio_to_black_video failed for {audio.name}")
    return dataclasses.replace(ctx, video_out=out)
```

---

### Step 6: compress_step

Fuente: `wx4/steps/compress.py`

**Solo existe en VideoPipeline.** AudioPipeline usa black_video_step unicamente.

Slices:
1. (Walking Skeleton) `compress_step(ctx)` -> `ctx.video_compressed`
2. `ctx.enhanced` existe -> usa enhanced como audio_source
3. `ctx.enhanced` no existe -> usa `ctx.src` como audio_source
4. `run_compression` lanza `RuntimeError` -> propaga sin silencio
5. `ctx.timings["compress"]` presente y `>= 0`

Nullables:
- `wx41.step_common.run_compression` -> `lambda *a, **kw: out_arg.touch()` (crea el archivo)

Cambios desde wx4:
- REEMPLAZAR: secuencia probe+lufs+encoder+bitrate -> `run_compression(src_video, audio_source, out, ctx.compress_ratio, ctx.step_progress)`
- REEMPLAZAR: timing manual -> `@timer("compress")`
- AGREGAR: audio_source es `ctx.enhanced` si existe, sino `ctx.src`
- ELIMINAR: `except RuntimeError: return dataclasses.replace(...)` -- raise siempre

---

## Fase 2: Pipeline + CLI (sin TDD en esta fase)

**wx41/pipeline.py**:
- `PipelineObserver` (Protocol @runtime_checkable): on_pipeline_start/end,
  on_step_start/end/skipped(reason), on_step_progress
- `NamedStep` (dataclass): name, fn, output_fn, skip_fn
- `StepDecision` (dataclass): name, would_run, output_path, reason
- `Pipeline.run(ctx)`, `Pipeline.dry_run(ctx)`
- `build_audio_pipeline(config, observers)` -> Pipeline
- `build_video_pipeline(config, observers)` -> Pipeline
- `MediaOrchestrator.run(src)`, `.dry_run(src)`
- `detect_media_type(src) -> str`
- `make_initial_ctx(src, config, media_type) -> PipelineContext`

**wx41/cli.py**:
- `app = typer.Typer()`
- `RichPipelineObserver`: implementa PipelineObserver con Rich Progress
- `main()` @app.command(): paths, compress, backend, force, skip_normalize,
  skip_enhance, dry_run, language, speakers, hf_token, whisper_model, device

---

## Verificacion

```bash
pytest wx41/tests/ -v
```

Tests al completar Fase 1 (27 total):
- `test_normalize_step.py`: 4 tests
- `test_enhance_step.py`: 4 tests
- `test_transcribe_step.py`: 5 tests
- `test_srt_step.py`: 3 tests
- `test_black_video_step.py`: 5 tests
- `test_compress_step.py`: 4 tests

---

## Archivos fuente (referencia durante implementacion)

| Archivo wx41 | Fuente wx4 | Tipo de cambio |
|--------------|-----------|----------------|
| `format_srt.py` | `wx4/format_srt.py` | Eliminar output_file de words_to_srt |
| `transcribe_aai.py` | `wx4/transcribe_aai.py` | submit + polling + progress_callback |
| `context.py` | `wx4/context.py` | Eliminar cache fields, agregar media_type |
| `step_common.py` | (nuevo) | @timer, atomic_output, temp_files, run_compression, PipelineState |
| `steps/normalize.py` | `wx4/steps/normalize.py` | Ver slices Step 1 |
| `steps/enhance.py` | `wx4/steps/enhance.py` | Ver slices Step 2 |
| `steps/transcribe.py` | `wx4/steps/transcribe.py` | Ver slices Step 3 |
| `steps/srt.py` | `wx4/steps/srt.py` | Ver slices Step 4 |
| `steps/black_video.py` | `wx4/steps/video.py` (parcial) | Ver slices Step 5 |
| `steps/compress.py` | `wx4/steps/compress.py` | Ver slices Step 6 |

---

## Diseno de pipeline.py y cli.py (de wx41.md)

Esta seccion contiene los patrones de implementacion concretos para Fase 2.

### PipelineState (step_common.py)

```python
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

Archivo de estado por fuente: `{src.stem}.wx41.json` en el mismo directorio.
`--force` usa `PipelineState.empty()` ignorando el estado guardado.

### atomic_output y temp_files (step_common.py)

```python
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
```

### @timer (step_common.py)

```python
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
```

`time.perf_counter()` reemplaza `time.time()` en todos los steps.

### run_compression (step_common.py)

```python
def run_compression(
    src_video: Path,
    audio_source: Path,
    out: Path,
    ratio: float,
    progress_callback=None,
) -> None:
    info = probe_video(src_video)
    lufs = (
        LufsInfo.from_measured(measure_audio_lufs(audio_source))
        if info.has_audio
        else LufsInfo.noop()
    )
    encoder = detect_best_encoder(force=None)
    bitrate = calculate_video_bitrate(info, ratio)
    compress_video(info, lufs, encoder, bitrate, out, progress_callback=progress_callback)
```

### Pipeline.run() con PipelineState

```python
def run(self, ctx: PipelineContext) -> PipelineContext:
    state_path = ctx.src.parent / f"{ctx.src.stem}.wx41.json"
    state = PipelineState.empty() if ctx.force else PipelineState.load(state_path)
    names = [s.name for s in self.steps]
    self._notify(lambda ob: ob.on_pipeline_start(names, ctx))
    try:
        for step in self.steps:
            user_skip = step.skip_fn is not None and step.skip_fn(ctx)
            if user_skip:
                state = state.mark_user_skipped(step.name)
                state.save(state_path)
                self._notify(lambda ob: ob.on_step_skipped(step.name, "user_skip", ctx))
                continue

            out = step.output_fn(ctx) if step.output_fn else None
            already_done = state.was_done(step.name) or (out is not None and out.exists())
            if already_done:
                if out is not None and out.exists() and step.ctx_setter:
                    ctx = step.ctx_setter(ctx, out)
                self._notify(lambda ob: ob.on_step_skipped(step.name, "already_done", ctx))
                continue

            ctx = dataclasses.replace(ctx, step_progress=self._make_progress(step.name))
            self._notify(lambda ob: ob.on_step_start(step.name, ctx))
            ctx = step.fn(ctx)
            state = state.mark_complete(step.name)
            state.save(state_path)
            self._notify(lambda ob: ob.on_step_end(step.name, ctx))
    finally:
        self._notify(lambda ob: ob.on_pipeline_end(ctx))
    return ctx
```

### Pipeline.dry_run() puro (ignora --force)

```python
def dry_run(self, ctx: PipelineContext) -> list[StepDecision]:
    state_path = ctx.src.parent / f"{ctx.src.stem}.wx41.json"
    state = PipelineState.load(state_path)
    simulated_ctx = _detect_intermediate_files(ctx)
    decisions = []
    for step in self.steps:
        user_skip = step.skip_fn is not None and step.skip_fn(simulated_ctx)
        if user_skip:
            decisions.append(StepDecision(step.name, False, None, "user_skip"))
            state = state.mark_user_skipped(step.name)
            continue

        out = step.output_fn(simulated_ctx) if step.output_fn else None
        already_done = state.was_done(step.name) or (out is not None and out.exists())
        if already_done:
            if out is not None and out.exists() and step.ctx_setter:
                simulated_ctx = step.ctx_setter(simulated_ctx, out)
            decisions.append(StepDecision(step.name, False, out, "already_done"))
        elif out is None and not step.skip_fn:
            decisions.append(StepDecision(step.name, True, None, "always_runs"))
        else:
            decisions.append(StepDecision(step.name, True, out, "not_done"))
    return decisions
```

`_detect_intermediate_files(ctx)` es funcion pura: escanea el directorio y puebla
`ctx.normalized`, `ctx.enhanced`, etc. segun archivos existentes. Sin I/O de escritura.

### build_audio_pipeline y build_video_pipeline

```python
from wx41.context import INTERMEDIATE_BY_STEP

_TRANSCRIBE = NamedStep(
    "transcribe", transcribe_step,
    output_fn=lambda ctx: ctx.src.parent / f"{ctx.src.stem}{INTERMEDIATE_BY_STEP['transcribe']}",
    ctx_setter=lambda ctx, p: dataclasses.replace(ctx, transcript_json=p),
)
_SRT = NamedStep(
    "srt", srt_step,
    output_fn=lambda ctx: ctx.src.parent / f"{ctx.src.stem}{INTERMEDIATE_BY_STEP['srt']}",
    ctx_setter=lambda ctx, p: dataclasses.replace(ctx, srt=p),
)

def build_audio_pipeline(config: PipelineConfig, observers) -> Pipeline:
    steps = [
        NamedStep(
            "normalize", normalize_step,
            output_fn=lambda ctx: ctx.src.parent / f"{ctx.src.stem}{INTERMEDIATE_BY_STEP['normalize']}",
            skip_fn=lambda ctx: config.skip_normalize,
            ctx_setter=lambda ctx, p: dataclasses.replace(ctx, normalized=p),
        ),
        NamedStep(
            "enhance", enhance_step,
            output_fn=lambda ctx: ctx.src.parent / f"{ctx.src.stem}{INTERMEDIATE_BY_STEP['enhance']}",
            skip_fn=lambda ctx: config.skip_enhance,
            ctx_setter=lambda ctx, p: dataclasses.replace(ctx, enhanced=p),
        ),
        _TRANSCRIBE,
        _SRT,
        NamedStep(
            "black_video", black_video_step,
            output_fn=lambda ctx: ctx.src.parent / f"{ctx.src.stem}{INTERMEDIATE_BY_STEP['video']}",
            ctx_setter=lambda ctx, p: dataclasses.replace(ctx, video_out=p),
        ),
    ]
    return Pipeline(steps, observers)

def build_video_pipeline(config: PipelineConfig, observers) -> Pipeline:
    steps = []
    if not config.skip_normalize:
        steps.append(NamedStep(
            "normalize", normalize_step,
            output_fn=lambda ctx: ctx.src.parent / f"{ctx.src.stem}{INTERMEDIATE_BY_STEP['normalize']}",
            skip_fn=lambda ctx: config.skip_normalize,
            ctx_setter=lambda ctx, p: dataclasses.replace(ctx, normalized=p),
        ))
    if not config.skip_enhance:
        steps.append(NamedStep(
            "enhance", enhance_step,
            output_fn=lambda ctx: ctx.src.parent / f"{ctx.src.stem}{INTERMEDIATE_BY_STEP['enhance']}",
            skip_fn=lambda ctx: config.skip_enhance,
            ctx_setter=lambda ctx, p: dataclasses.replace(ctx, enhanced=p),
        ))
    steps.extend([
        _TRANSCRIBE,
        _SRT,
        NamedStep(
            "compress", compress_step,
            output_fn=lambda ctx: ctx.src.parent / f"{ctx.src.stem}{INTERMEDIATE_BY_STEP['compress']}",
            ctx_setter=lambda ctx, p: dataclasses.replace(ctx, video_compressed=p),
        ),
    ])
    return Pipeline(steps, observers)
```

### MediaOrchestrator

```python
class MediaOrchestrator:
    def __init__(self, config: PipelineConfig, observers):
        self._config = config
        self._observers = observers

    def run(self, src: Path) -> PipelineContext:
        media_type = detect_media_type(src)
        ctx = make_initial_ctx(src, self._config, media_type=media_type)
        pipeline = self._build_pipeline(media_type)
        return pipeline.run(ctx)

    def dry_run(self, src: Path) -> tuple[str, list[StepDecision]]:
        media_type = detect_media_type(src)
        ctx = make_initial_ctx(src, self._config, media_type=media_type)
        pipeline = self._build_pipeline(media_type)
        return media_type, pipeline.dry_run(ctx)

    def _build_pipeline(self, media_type: str) -> Pipeline:
        if media_type == MediaType.VIDEO:
            return build_video_pipeline(self._config, self._observers)
        return build_audio_pipeline(self._config, self._observers)
```

### PipelineObserver (Protocol)

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class PipelineObserver(Protocol):
    def on_pipeline_start(self, step_names: list[str], ctx: PipelineContext) -> None: ...
    def on_step_start(self, name: str, ctx: PipelineContext) -> None: ...
    def on_step_end(self, name: str, ctx: PipelineContext) -> None: ...
    def on_step_skipped(self, name: str, reason: str, ctx: PipelineContext) -> None: ...
    def on_step_progress(self, name: str, done: int, total: int) -> None: ...
    def on_pipeline_end(self, ctx: PipelineContext) -> None: ...
```

`reason` en `on_step_skipped`: `"user_skip"` | `"already_done"`.

### RichPipelineObserver (cli.py)

```python
class RichPipelineObserver:
    def __init__(self, console):
        self._console = console
        self._progress = None
        self._task_ids = {}

    def reset(self) -> None:
        self._task_ids.clear()

    def on_pipeline_start(self, step_names, ctx):
        self._progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold]{task.description}"),
            BarColumn(),
            TimeElapsedColumn(),
            transient=True,
            console=self._console,
        )
        self._progress.start()

    def on_step_start(self, name, ctx):
        task_id = self._progress.add_task(name, total=None)
        self._task_ids[name] = task_id

    def on_step_end(self, name, ctx):
        self._progress.update(self._task_ids[name], completed=1, total=1)
        self._progress.update(self._task_ids[name], visible=False)

    def on_step_skipped(self, name, reason, ctx):
        self._console.print(f"  [dim]{name}: skipped ({reason})[/dim]")

    def on_step_progress(self, name, done, total):
        if name in self._task_ids:
            self._progress.update(self._task_ids[name], completed=done, total=total)

    def on_pipeline_end(self, ctx):
        if self._progress:
            self._progress.stop()
```

`reset()` limpia `_task_ids` entre archivos en modo multi-archivo.
`transient=True`: la barra desaparece al terminar.
`total=None` en `add_task`: spinner pulsante hasta recibir progreso real.

### AssemblyAI: submit + polling (transcribe_aai.py)

```python
def transcribe_assemblyai(
    audio: Path,
    lang=None,
    speakers=None,
    progress_callback=None,
):
    aai.settings.api_key = os.environ.get("ASSEMBLY_AI_KEY") or _raise_no_key()
    config = aai.TranscriptionConfig(...)

    transcript = aai.Transcriber(config=config).submit(str(audio))
    if progress_callback:
        progress_callback(0, 3)

    _PROCESSING = {aai.TranscriptStatus.queued, aai.TranscriptStatus.processing}
    while transcript.status in _PROCESSING:
        time.sleep(3)
        transcript = transcript.wait_for_completion()
        if transcript.status == aai.TranscriptStatus.processing and progress_callback:
            progress_callback(1, 3)

    if transcript.status == aai.TranscriptStatus.error:
        raise RuntimeError(f"AssemblyAI error: {transcript.error}")

    if progress_callback:
        progress_callback(3, 3)
    # ... generar txt y json ...
```

Los 3 pasos: (0) uploading/queued, (1) processing, (3) completed.

### Signal handling (cli.py)

```python
_stop = threading.Event()

def _handle_signal(sig: int, _frame) -> None:
    _stop.set()

# En main():
signal.signal(signal.SIGINT, _handle_signal)
signal.signal(signal.SIGTERM, _handle_signal)

for src in sources:
    if _stop.is_set():
        break
    observer.reset()
    orchestrator.run(src)
```

### Mapa de impacto en tests

| Que cambia | Impacto en tests existentes |
|------------|----------------------------|
| Nuevo `black_video_step` (extraido de video_step) | Renombrar TestVideoStep; eliminar tests de compresion interna |
| Eliminar `cache_check_step` y `cache_save_step` | Eliminar TestCacheCheckStep y TestCacheSaveStep |
| Eliminar skip interno de normalize/enhance | Eliminar tests de skip por cache_hit |
| `PipelineState` reemplaza `ctx.cache_hit` y `ctx.cache` | Fixtures de ctx pierden esos campos |
| `on_step_skipped` gana `reason: str` | test_pipeline.py: TestPipelineCallbacks |
| dry_run ignora force | test_pipeline.py: TestPipelineDryRun |
| `build_audio_pipeline` / `build_video_pipeline` reemplazan `build_steps()` | test_pipeline.py: TestBuildSteps (split) |
| Nuevo `MediaOrchestrator` | Nuevo TestMediaOrchestrator |
| Typer reemplaza argparse | test_cli.py: todos |
| `run_compression` extraido a step_common.py | test_steps.py: TestVideoStep, TestCompressStep |
| AssemblyAI usa submit + polling | test_steps.py: TestTranscribeStep (mock submit) |
