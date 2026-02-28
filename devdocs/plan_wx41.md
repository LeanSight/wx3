# plan_wx41.md - Implementacion ATDD/TDD

Fecha: 2026-02-28
Ref: devdocs/standard-atdd-tdd.md (metodologia), devdocs/arquitectura.md (modularidad)

---

## Objetivos funcionales

| Objetivo | Componente | Seccion del plan |
|----------|------------|-----------------|
| **Encadenado de steps** | `Pipeline.run()` ejecuta `NamedStep` en orden; cada step recibe y retorna `PipelineContext` inmutable | S1 |
| **Activacion/desactivacion declarativa** | `skip_fn` declarado en el builder capturando `PipelineConfig`; el step no sabe que existe el flag | S3 |
| **Visualizacion en UI** | `PipelineObserver` Protocol; `RichPipelineObserver` en cli.py | S1 |
| **Resumability** | `PipelineState` serializa steps completados en disco | S5 |
| **Dry run** | `Pipeline.dry_run()` sin ejecutar ningun step | S8 |

---

## Arquitectura de Modularidad (Referencia: devdocs/arquitectura.md)

Hay dos categorias de parametros que NO deben mezclarse:

### Categoria A: Flags de Orquestacion (PipelineConfig, campos tipados)
Son responsabilidad del PIPELINE, no del step. El builder los captura en clausuras.
```
--no-normalize  ->  PipelineConfig.skip_normalize  ->  skip_fn=lambda ctx: config.skip_normalize
--no-enhance    ->  PipelineConfig.skip_enhance    ->  skip_fn=lambda ctx: config.skip_enhance
--force         ->  PipelineConfig.force           ->  Pipeline.run() los evalua
--compress      ->  PipelineConfig.compress_ratio  ->  compress_step lo lee del ctx
```

### Categoria B: Configuracion de Infraestructura (StepConfig, bolsa settings)
Son responsabilidad del STEP. El step define su propio dataclass, el builder lo inyecta.
```
--aai-key       ->  TranscribeConfig.api_key   ->  config.settings["transcribe"]
--backend       ->  TranscribeConfig.backend   ->  config.settings["transcribe"]
--hf-token      ->  TranscribeConfig.hf_token  ->  config.settings["transcribe"]
```

### PipelineContext: solo Estado Observable (campos tipados, inmutable)
El contexto NO tiene parametros de infraestructura. Solo tiene el estado del pipeline:
archivos generados, timings, y parametros de negocio compartidos (language, speakers).
```python
@dataclass(frozen=True)
class PipelineContext:
    src: Path
    force: bool = False
    language: Optional[str] = None
    speakers: Optional[int] = None
    speaker_names: Dict[str, str] = field(default_factory=dict)
    compress_ratio: Optional[float] = None
    srt_mode: str = "speaker-only"
    step_progress: Optional[Callable] = None
    timings: Dict[str, float] = field(default_factory=dict)
    # Archivos intermedios (Estado)
    normalized: Optional[Path] = None
    enhanced: Optional[Path] = None
    transcript_txt: Optional[Path] = None
    transcript_json: Optional[Path] = None
    srt: Optional[Path] = None
    video_out: Optional[Path] = None
    video_compressed: Optional[Path] = None
```

### PipelineConfig: Flags de orquestacion + bolsa de StepConfigs
```python
@dataclass(frozen=True)
class PipelineConfig:
    force: bool = False
    skip_normalize: bool = False
    skip_enhance: bool = False
    compress_ratio: Optional[float] = None
    language: Optional[str] = None
    speakers: Optional[int] = None
    # Bolsa generica de configuraciones de infraestructura por step
    # Cada step define su propio StepConfig y lo busca en esta bolsa
    settings: Dict[str, Any] = field(default_factory=dict)
```

### Flujo completo CLI -> Pipeline -> Step
```
CLI
 |-- flags de orquestacion  --> PipelineConfig (campos tipados)
 |-- flags de infraestructura -> PipelineConfig.settings["step_name"] = StepConfig(...)
         |
         v
    MediaOrchestrator.run(src)
         |
         v
    make_initial_ctx(src, config)  <- propaga language, speakers, compress_ratio, force al ctx
         |
         v
    build_audio_pipeline(config, observers)
         |-- _step("normalize", normalize_step, "normalized",
         |         skip_fn=lambda ctx: config.skip_normalize)   <- clausura sobre config
         |-- _step("enhance", enhance_step, "enhanced",
         |         skip_fn=lambda ctx: config.skip_enhance)
         |-- transcribe (NamedStep especial):
         |       t_cfg = config.settings.get("transcribe", TranscribeConfig())
         |       fn = lambda ctx: transcribe_step(ctx, t_cfg)   <- inyeccion de StepConfig
         |-- _step("srt", srt_step, "srt")
         |-- _step("video", black_video_step, "video_out")
         |
         v
    Pipeline.run(ctx)
         |-- evalua skip_fn(ctx) por step -> salta si True
         |-- evalua output ya existe -> salta si ya_done
         |-- ejecuta step(ctx) -> ctx nuevo
```

---

## Estructura wx41/ (completa)

```
wx41/
  __init__.py

  # logic (cero I/O)
  format_convert.py
  format_srt.py           words_to_srt retorna str (sin output_file)
  speakers.py

  # infrastructure (wrappers I/O)
  audio_extract.py
  audio_encode.py
  audio_enhance.py
  audio_normalize.py
  video_black.py
  video_merge.py
  compress_video.py
  transcribe_aai.py       submit + polling + progress_callback + api_key arg
  transcribe_wx3.py
  model_cache.py

  # application shared
  context.py              PipelineContext (tipado), PipelineConfig (con settings), INTERMEDIATE_BY_STEP
  step_common.py          @timer, atomic_output, temp_files, run_compression, PipelineState
  pipeline.py             NamedStep, Pipeline, PipelineObserver, StepDecision,
                          _step factory, build_audio_pipeline, build_video_pipeline,
                          MediaOrchestrator, detect_media_type, make_initial_ctx

  cli.py                  Typer app, RichPipelineObserver, main()

  steps/
    __init__.py
    normalize.py
    enhance.py
    transcribe.py         TranscribeConfig + transcribe_step(ctx, config)
    srt.py
    black_video.py
    compress.py

  tests/
    __init__.py
    conftest.py           make_ctx helper
    test_acceptance.py
    test_normalize_step.py
    test_enhance_step.py
    test_transcribe_step.py
    test_srt_step.py
    test_black_video_step.py
    test_compress_step.py
```

---

## Decisiones de diseno

1. **PipelineContext tipado**: campos especificos por nombre (`ctx.normalized`, `ctx.enhanced`).
   Razon: type safety, autocompletado, refactor seguro. NO un dict generico.

2. **Dos categorias de config separadas**: flags de orquestacion en `PipelineConfig` (tipados),
   configuracion de infraestructura en `PipelineConfig.settings` (bolsa generica por step).

3. **Steps agnósticos al pipeline**: el step solo recibe `ctx` (y su `StepConfig` si lo necesita).
   No sabe si esta habilitado, si hay observers, ni si es un dry run.

4. **skip_fn en el builder**: la logica de activacion/desactivacion se declara en `build_*_pipeline`,
   capturando `PipelineConfig` en clausura. Ningun step tiene logica de skip interna.

5. **StepConfig inyectado por clausura**: el builder hace
   `lambda ctx: transcribe_step(ctx, t_cfg)`. La funcion resultante tiene firma
   `(PipelineContext) -> PipelineContext` compatible con `NamedStep.fn`.

6. **make_initial_ctx propaga params de negocio**: `language`, `speakers`, `compress_ratio`,
   `force` van del `PipelineConfig` al `PipelineContext` en `make_initial_ctx`.
   No van via `settings` porque son parametros de negocio compartidos por varios steps.

7. **words_to_srt pura**: retorna solo `str`. srt_step escribe el archivo.

8. **Nullables via monkeypatch**: para infrastructure. NO mockear step_common ni logic.

9. **State-Based assertions**: NUNCA `assert_called_with`. Verificar ctx fields y archivos en disco.

---

## S1 — Walking Skeleton: transcribe + pipeline base

### AT (criterio de aceptacion):
```python
orchestrator.run(audio.m4a)
assert ctx.transcript_txt.exists()
assert ctx.transcript_json.exists()
```

### Lo que crea el S1:
- `context.py`: PipelineContext tipado + PipelineConfig con settings
- `step_common.py`: solo @timer
- `steps/transcribe.py`: TranscribeConfig + transcribe_step(ctx, config)
- `pipeline.py`: NamedStep, Pipeline.run() minimo, _step factory,
                 build_audio_pipeline (solo transcribe), MediaOrchestrator,
                 make_initial_ctx, PipelineObserver Protocol
- `cli.py`: Typer app minimo con args de transcripcion
- `tests/conftest.py`: make_ctx
- `tests/test_acceptance.py`: AT del S1
- `tests/test_transcribe_step.py`: unit tests del step

### Slices del S1:

**Slice 1 - Pipeline base + transcribe assemblyai (AT rojo -> verde)**
Test: AT produces transcript files
Produce: context.py, step_common.py, transcribe_step, pipeline.py, test_acceptance.py
Commit + Push

**Slice 2 - whisper backend**
Test: transcribe_step con TranscribeConfig(backend="whisper") usa transcribe_with_whisper
Commit + Push

**Slice 3 - backend desconocido**
Test: RuntimeError("Unknown transcribe_backend: ...")
Commit + Push

**Slice 4 - usa enhanced si existe**
Test: transcribe_step usa ctx.enhanced como audio cuando esta seteado
Commit + Push

**Slice 5 - timing**
Test: ctx.timings["transcribe"] >= 0
Commit + Push

**Slice 6 - CLI end-to-end**
Test: CLI con --aai-key llama al orchestrator correctamente
CLI construye TranscribeConfig y lo mete en settings["transcribe"]
Commit + Push

### Verificacion S1 completo:
```bash
pytest wx41/tests/ -v
# 7+ tests GREEN
```

---

## S2 — Harvest: port de todos los unit tests de steps

Protocolo por slice:
1. Test RED (cero produccion nueva)
2. Mejorar mensaje de fallo
3. Produccion minima -> GREEN
4. COMMIT + PUSH

### Step 1: normalize_step (sin StepConfig, solo usa ctx)
Slices:
1. normalize_step(ctx) -> ctx.normalized + archivo _normalized.m4a
2. extract_to_wav False -> RuntimeError
3. to_aac False -> RuntimeError, tmp files limpios
4. timings["normalize"] >= 0

Nullables (monkeypatch):
- wx41.audio_extract.extract_to_wav -> lambda src, dst: True
- wx41.audio_normalize.normalize_lufs -> lambda src, dst, **kw: None
- wx41.audio_encode.to_aac -> lambda src, dst, **kw: (dst.touch(), True)[1]

### Step 2: enhance_step (sin StepConfig, solo usa ctx)
Slices:
1. enhance_step(ctx con normalized) -> ctx.enhanced + archivo _enhanced.m4a
2. ctx.normalized is None -> usa ctx.src
3. to_aac False -> RuntimeError
4. timings["enhance"] >= 0

Nullables:
- wx41.model_cache._get_model -> lambda *a, **kw: object()
- wx41.audio_enhance.apply_clearvoice -> lambda src, dst, cv, **kw: dst.touch()
- wx41.audio_encode.to_aac -> lambda src, dst, **kw: (dst.touch(), True)[1]

### Step 3: transcribe_step (YA HECHO en S1, ampliar slices)
Slices adicionales: ver S1 slices 2-5.

### Step 4: srt_step (sin StepConfig)
Slices:
1. srt_step(ctx con transcript_json) -> ctx.srt + archivo .srt con contenido
2. ctx.transcript_json is None -> RuntimeError
3. timings["srt"] >= 0

### Step 5: black_video_step (sin StepConfig)
Slices:
1. black_video_step(ctx con enhanced) -> ctx.video_out + _timestamps.mp4
2. enhanced None, normalized existe -> usa normalized
3. enhanced y normalized None -> usa ctx.src
4. audio_to_black_video False -> RuntimeError
5. timings["black_video"] >= 0

Nullables:
- wx41.video_black.audio_to_black_video -> lambda audio, out: (out.touch(), True)[1]

### Step 6: compress_step (sin StepConfig, usa ctx.compress_ratio)
Slices:
1. compress_step(ctx) -> ctx.video_compressed
2. ctx.enhanced existe -> usa enhanced como audio_source
3. ctx.enhanced no existe -> usa ctx.src
4. run_compression lanza RuntimeError -> propaga
5. timings["compress"] >= 0

Nullables:
- wx41.step_common.run_compression -> lambda *a, **kw: out.touch()

---

## S3 — Cablear normalize + enhance al pipeline

AT:
```python
assert ctx.normalized.exists()
assert ctx.enhanced.exists()
assert ctx.transcript_txt.exists()
```

build_audio_pipeline agrega:
```python
_step("normalize", normalize_step, "normalized",
      skip_fn=lambda ctx: config.skip_normalize),
_step("enhance", enhance_step, "enhanced",
      skip_fn=lambda ctx: config.skip_enhance),
```

CLI agrega:
```python
skip_normalize: bool = typer.Option(False, "--no-normalize"),
skip_enhance:   bool = typer.Option(False, "--no-enhance"),
```
PipelineConfig.skip_normalize y skip_enhance ya existen como campos tipados.

---

## S4 — Audio pipeline completo (srt + black_video)

AT:
```python
assert ctx.srt.exists()
assert ctx.video_out.exists()
```

---

## S5 — Resumability (PipelineState)

AT:
```python
orchestrator.run(audio.m4a)
ctx.enhanced.unlink()
orchestrator.run(audio.m4a)
assert state.was_done("normalize")
assert ctx.transcript_txt.exists()
```

step_common.py agrega PipelineState.
Pipeline.run() agrega logica de was_done() y ctx_setter para restaurar ctx.

---

## S6 — Whisper backend (ya cubierto en S1 Slice 2)

AT:
```python
orchestrator.run(audio.m4a, config con TranscribeConfig(backend="whisper"))
assert ctx.transcript_txt.exists()
```

---

## S7 — Video pipeline (compress)

AT:
```python
orchestrator.run(video.mp4)
assert ctx.video_compressed.exists()
```

build_video_pipeline agrega compress_step.
detect_media_type determina si src es audio o video.

---

## S8 — Dry run

AT:
```python
decisions = orchestrator.dry_run(audio.m4a)
assert not any_file_created
assert decisions[0].would_run == True
```

Pipeline.dry_run() retorna list[StepDecision] sin ejecutar ningun step.
_detect_intermediate_files puebla ctx desde disco de forma pura.
