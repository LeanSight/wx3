# plan_wx41_modular.md - Mirada Realmente Modular (ATDD/TDD)

## Arquitectura de la Mirada Modular

### 1. PipelineContext Desacoplado
```python
@dataclass(frozen=True)
class PipelineContext:
    src: Path
    force: bool = False
    data: Dict[str, Any] = field(default_factory=dict)
    timings: Dict[str, float] = field(default_factory=dict)
    step_progress: Optional[Callable[[int, int], None]] = None
```
No hay propiedades como `ctx.normalized` o `ctx.enhanced`. Los steps usan `ctx.data["normalized"]`.

### 2. NamedStep como Descriptor de Step
```python
@dataclass(frozen=True)
class NamedStep:
    name: str
    fn: Callable[[PipelineContext], PipelineContext]
    # Suffix para el output automático
    output_suffix: Optional[str] = None
```

### 3. Configuración Modular por Step (StepConfig)
Cada step define su propia configuración inmutable. El `Pipeline` se construye pasando estas configuraciones pre-formadas.

### 4. CLI por Composición (Typer Modular)
El CLI principal (`cli.py`) compone los argumentos que "publican" los steps. Si un step necesita una API Key, el CLI la pide, la mete en el `StepConfig` y la pasa al `Builder`.

---

## Objetivos del S1 (Walking Skeleton Modular)

1. **Pipeline.run() Genérico**: Ejecuta steps sobre un `PipelineContext` que usa un diccionario interno.
2. **transcribe_step Modular**:
   - Define su propio `TranscribeConfig`.
   - Se inyecta en el pipeline con su configuración ya "armada".
   - No sabe nada de `PipelineConfig` global.
3. **CLI Modular**: El CLI agrupa los parámetros de transcripción y construye el `TranscribeConfig`.
4. **Validación ATDD**:
   ```python
   orchestrator.run(src)
   assert ctx.data["transcript_txt"].exists()
   assert ctx.data["transcript_json"].exists()
   ```

---

## Slices S1 (Modular)

### Slice 1: Contexto y Pipeline Base
- `PipelineContext` genérico (con dict).
- `NamedStep` base.
- `Pipeline.run()` básico que llame a los steps.
- **Test**: Un pipeline con un step "dummy" que escriba en `ctx.data`.

### Slice 2: Transcribe Step Modular
- `TranscribeConfig` inyectable.
- `transcribe_step(ctx, config)` que use `ctx.data` para guardar resultados.
- **Test**: Transcribe step aislado con su config manual.

### Slice 3: CLI Modular (Composición)
- `Typer` pidiendo argumentos para la transcripción.
- Construcción del pipeline inyectando el config del CLI.
- **Test (AT)**: `python -m wx41.cli --aai-key X audio.m4a` -> Genera archivos.

---

## Por qué esto es "Realmente Modular":
- **Independencia**: Para añadir el step de `Normalize`, solo creas el archivo, defines su config, y lo añades al pipeline en el builder. No tocas `context.py`.
- **Escalabilidad**: El CLI crece orgánicamente añadiendo los parámetros que cada step necesita, sin que el núcleo del pipeline sepa qué son.
- **A-Frame Puro**: El estado (`Context`) y la lógica (`Step`) están totalmente desacoplados de la infraestructura (`Config`).
