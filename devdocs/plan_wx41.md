# plan_wx41.md - Implementación ATDD/TDD Modular

Fecha: 2026-02-28
Ref: devdocs/standard-atdd-tdd.md, devdocs/arquitectura.md

---

## Estado de Implementación (2026-03-02)

| Objetivo | Estado | Archivos |
|----------|--------|----------|
| Encadenado de steps | ✅ IMPLEMENTADO | pipeline.py |
| Configuración declarativa (dinámica) | ✅ IMPLEMENTADO | steps/__init__.py (STEP_REGISTRY) |
| Visualización UI | ✅ IMPLEMENTADO | ui/progress.py |
| Resumability (default, force override) | ✅ IMPLEMENTADO | pipeline.py |
| Dry run | ✅ IMPLEMENTADO | pipeline.py, context.py |
| Control+C graceful | ✅ IMPLEMENTADO | ui/interrupt.py |
| Lazy imports | ✅ IMPLEMENTADO | transcribe_aai.py, transcribe_whisper.py, model_cache.py |
| CLI con opciones | ✅ IMPLEMENTADO | cli.py |

### Tests
```
pytest wx41/tests/ -v
11 passed
```

---

## Objetivos wx41

Investigar la forma más idiomática y pythónica en 2026 de programar, y reimplementar desde cero pipeline.py y cli.py con soporte para:

- Encadenado de steps
- Activación/desactivación y configuración de steps de forma declarativa (orientado a modularidad)
- Visualización en una UI
- Retoma correcta del proceso si se detiene (resumability)
- Implementación de dry run para simular la ejecución

---

## 1. Arquitectura de Desacoplamiento Total

### PipelineContext (Genérico)
```python
@dataclass(frozen=True)
class PipelineContext:
    src: Path
    force: bool = False
    dry_run: bool = False
    interrupted: bool = False
    outputs: Dict[str, Path] = field(default_factory=dict)
    timings: Dict[str, float] = field(default_factory=dict)
    step_progress: Optional[Callable[[int, int], None]] = None
```

### PipelineConfig (Transporte)
```python
@dataclass(frozen=True)
class PipelineConfig:
    force: bool = False
    settings: Dict[str, Any] = field(default_factory=dict) # Bolsa de StepConfigs
```

### Step Modular (Ejemplo: Transcribe)
```python
@dataclass(frozen=True)
class TranscribeConfig:
    backend: str = "assemblyai"
    api_key: Optional[str] = None
    language: Optional[str] = None
    # ... otros campos ...

def transcribe_step(ctx: PipelineContext, config: TranscribeConfig) -> PipelineContext:
    # 1. Busca su input por nombre (desacoplado de la estructura del ctx)
    audio = ctx.outputs.get("enhanced") or ctx.outputs.get("normalized") or ctx.src
    # 2. Ejecuta usando su config inyectada
    txt, jsn = ...
    # 3. Registra sus resultados por nombre
    new_outputs = {**ctx.outputs, "transcript_txt": txt, "transcript_json": jsn}
    return dataclasses.replace(ctx, outputs=new_outputs)
```

---

## 2. S1 — Walking Skeleton (Validación de Modularidad)

El objetivo de este slice es demostrar que el pipeline puede ejecutar un step sin que el contexto tenga propiedades hardcodeadas.

### AT:
```python
orchestrator.run(audio.m4a)
assert "transcript_txt" in ctx.outputs
assert ctx.outputs["transcript_txt"].exists()
```

### Slices del S1:

**Slice 1: El Núcleo Genérico**
- `context.py`: `PipelineContext` con `outputs: Dict`.
- `pipeline.py`: `Pipeline.run()` que itera steps y propaga el mapa de outputs.
- `step_common.py`: `@timer`.
- **Test**: Pipeline con un step "dummy" que guarda un archivo en `outputs["dummy"]`.

**Slice 2: Transcribe como Plug-in**
- `steps/transcribe.py`: `TranscribeConfig` + `transcribe_step(ctx, config)`.
- **Test**: `transcribe_step` unitario inyectándole una config manual.

**Slice 3: CLI Modular (Composición de bolsa de settings)**
- `cli.py`: Typer captura argumentos, crea `TranscribeConfig`, lo mete en `config.settings["transcribe"]`.
- `MediaOrchestrator` / `Builder`: Extrae de la bolsa e instancia.
- **Test (AT)**: Ejecución completa desde CLI.

---

## 3. Tabla de Registro de Steps

| Step | Nombre Output en `ctx.outputs` | Dependencia (Input) | Estado |
|------|-------------------------------|---------------------|--------|
| `normalize` | `"normalized"` | `ctx.src` | ⏳ PENDIENTE |
| `enhance` | `"enhanced"` | `"normalized"` o `ctx.src` | ⏳ PENDIENTE |
| `transcribe` | `"transcript_txt/json"`| `"enhanced"` o `"normalized"` o `ctx.src` | ✅ IMPLEMENTADO |
| `srt` | `"srt"` | `"transcript_json"` | ⏳ PENDIENTE |
| `black_video`| `"video_out"` | Cualquiera de audio anterior | ⏳ PENDIENTE |
| `compress` | `"video_compressed"` | `"video_out"` | ⏳ PENDIENTE |

---

## 4. Dinamismo en el Pipeline

Implementado via **Step Registry** (`steps/__init__.py`):
- `STEP_REGISTRY`: Dict[str, Callable] - funciones de steps
- `STEP_OUTPUT_FN_REGISTRY`: Dict[str, Callable] - funciones de output
- `register_step(name, fn, output_fn)`: registra un step dinámicamente

Al construir el pipeline (`build_pipeline`):
1. El builder itera sobre `config.settings`
2. Para cada entry en settings, busca en STEP_REGISTRY
3. Si existe, crea NamedStep con la función y su output_fn
4. Resumability: si outputs existen en disco, salta el step
5. Force: con force=True, ignora resumability y ejecuta siempre

---

## 5. Decisiones Técnicas Finales

1. **NamedStep genérico**: `fn: Callable[[PipelineContext], PipelineContext]`. El builder se encarga de que esa función sea una clausura que ya tiene inyectada su `StepConfig`.
2. **Context Setter genérico**: El pipeline registra automáticamente el resultado de `NamedStep.output_fn` en `ctx.outputs[step.name]` si está definido.
3. **Inmutabilidad**: `PipelineContext` es `frozen=True`. Cada step retorna una copia nueva con `outputs` y `timings` actualizados.
