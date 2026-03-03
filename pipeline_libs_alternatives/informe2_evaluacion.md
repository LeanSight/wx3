# Informe 2: Evaluacion por Libreria vs 5 Objetivos wx41

Fecha: 2026-02-28

---

## Los 5 Objetivos wx41

1. **Encadenado de steps** - Capacidad de definir flujo de pasos
2. **Configuracion declarativa** - Activation/desactivacion via YAML/JSON
3. **Visualizacion en UI** - Representacion grafica del pipeline
4. **Resumability** - Reanudar si se detiene
5. **Dry run** - Simular ejecucion sin ejecutar

---

## pipefunc

### Score: 2/5

| Objetivo | Cumple | Justificacion |
|----------|--------|---------------|
| Encadenado | ✅ Si | `@pipefunc(output_name="x")` + DAG automatico por parametros |
| Declarativo | ❌ No | No tiene YAML/JSON. Solo codigo Python. |
| Visualizacion | ⚠️ Parcial | `pipeline.visualize()` genera grafico pero no es UI |
| Resumability | ⚠️ Parcial | Cache automatico pero no controla archivos existentes |
| Dry run | ❌ No | No tiene modo simulacion |

### Codigo

```python
@pipefunc(output_name="normalized")
def normalize(audio: Path) -> Path:
    return audio

@pipefunc(output_name=("txt", "json"))
def transcribe(audio: Path, backend: str) -> Tuple[Path, Path]:
    ...

pipeline = Pipeline([normalize, transcribe])
result = pipeline("json", audio=src, backend="whisper")
```

### Conclusion

Adecuado para encadenado pero insuficiente para objetivos declarativos.

---

## justpipe

### Score: 2/5

| Objetivo | Cumple | Justificacion |
|----------|--------|---------------|
| Encadenado | ✅ Si | `@pipe.step(to="x")` define flujo |
| Declarativo | ❌ No | Solo codigo, sin YAML/JSON |
| Visualizacion | ⚠️ Parcial | Eventos para UI pero sin built-in |
| Resumability | ❌ No | No tiene cache ni resume |
| Dry run | ❌ No | No tiene modo simulacion |

### Codigo

```python
@pipe.step(to="transcribe")
def normalize(state):
    state.normalized = state.audio_path

@pipe.step()
def transcribe(state, backend: str):
    ...

pipe = Pipe()
async for event in pipe.run(state):
    ...
```

### Conclusion

Zero dependencies pero muy basico. No apt para objetivos 2-5.

---

## pypyr

### Score: 3/5

| Objetivo | Cumple | Justificacion |
|----------|--------|---------------|
| Encadenado | ✅ Si | Steps secuenciales en YAML |
| Declarativo | ✅ Si | YAML nativo con `skip`, `foreach`, `while` |
| Visualizacion | ❌ No | No tiene visualizacion |
| Resumability | ❌ No | No tiene cache ni resume |
| Dry run | ✅ Si | `pypyr --dry-run` nativo |

### Codigo

```yaml
# pipeline.yaml
steps:
  - name: wx41.normalize
  - name: wx41.transcribe
    skip: false
```

```bash
pypyr pipeline.yaml --dry-run
```

### Conclusion

Excelente para declarativo y dry-run pero carece de visualizacion y resumability.

---

## pipelime

### Score: 4/5

| Objetivo | Cumple | Justificacion |
|----------|--------|---------------|
| Encadenado | ✅ Si | `Piper() << Stage()` encadena |
| Declarativo | ✅ Si | YAML/JSON para configuracion |
| Visualizacion | ✅ Si | UI integrada |
| Resumability | ⚠️ Parcial | Cache pero no resume completo |
| Dry run | ✅ Si | `--dry-run` flag |

### Codigo

```python
piper = Piper()
piper << NormalizeStage()
piper << TranscribeStage()

piper.run(str(src), dry_run=True)
```

### Conclusion

La mejor de las librerías implementadas. Cumple 4/5 objetivos.

---

## pipeco

### Score: 1/5

| Objetivo | Cumple | Justificacion |
|----------|--------|---------------|
| Encadenado | ⚠️ Parcial | Pipes pero API inestable |
| Declarativo | ❌ No | Solo Python |
| Visualizacion | ❌ No | No tiene |
| Resumability | ❌ No | No tiene |
| Dry run | ❌ No | No tiene |

### Codigo

```python
class TranscribeStep(Step):
    audio_in: Path
    transcript: Path
    
    def run(self):
        ...

pipeline = Pipeline(steps=[TranscribeStep.define()])
```

### Conclusion

Muy nueva (0.1.3), API inestable. No recomendada.

---

## dynapipeline

### Score: 1/5

| Objetivo | Cumple | Justificacion |
|----------|--------|---------------|
| Encadenado | ✅ Si | StageGroup con execution strategy |
| Declarativo | ❌ No | Solo Python |
| Visualizacion | ❌ No | No tiene |
| Resumability | ❌ No | No tiene |
| Dry run | ❌ No | No tiene |

### Codigo

```python
stage = StageGroup(
    stages=[NormalizeStage(), TranscribeStage()],
    execution_strategy=SequentialExecutionStrategy()
)
pipeline = factory.create_pipeline(groups=[stage])
```

### Conclusion

Async-first pero sin declarativo ni features avanzados.

---

## dynaflow

### Score: 1/5

| Objetivo | Cumple | Justificacion |
|----------|--------|---------------|
| Encadenado | ✅ Si | JSON/ASL define flujo |
| Declarativo | ⚠️ Parcial | JSON pero no YAML |
| Visualizacion | ❌ No | No tiene |
| Resumability | ❌ No | No tiene |
| Dry run | ❌ No | No tiene |

### Codigo

```python
flow_def = {
    "StartAt": "normalize",
    "States": {
        "normalize": {"Type": "Pass", "Next": "transcribe"},
        "transcribe": {"Type": "Task", "Function": {"Handler": "x"}}
    }
}
flow = DynaFlow(flow_def, functions=get_functions())
```

### Conclusion

Paradigma diferente (AWS Step Functions). No apt para wx41.

---

## Custom wx41 (Base)

### Score: 3/5

| Objetivo | Cumple | Justificacion |
|----------|--------|---------------|
| Encadenado | ✅ Si | NamedStep con Pipeline.run() |
| Declarativo | ⚠️ Parcial | dict settings pero no YAML |
| Visualizacion | ❌ No | No tiene |
| Resumability | ✅ Si | Check archivos existentes |
| Dry run | ❌ No | No tiene |

### Codigo

```python
@dataclass(frozen=True)
class PipelineContext:
    src: Path
    outputs: Dict[str, Path]

def build_pipeline(config):
    if "transcribe" in config.settings:
        steps.append(NamedStep(...))
    return Pipeline(steps)

orchestrator.run(src)  # Resume si archivos existen
```

### Conclusion

Cumple arquitectura de plan_wx41 pero faltan visualizacion y dry-run.

---

## Tabla Resumen

| Libreria | Encadenado | Declarativo | Visualizacion | Resumability | Dry run | Total |
|----------|------------|-------------|---------------|--------------|---------|-------|
| pipelime | ✅ | ✅ | ✅ | ⚠️ | ✅ | **4/5** |
| pypyr | ✅ | ✅ | ❌ | ❌ | ✅ | **3/5** |
| Custom wx41 | ✅ | ⚠️ | ❌ | ✅ | ❌ | **3/5** |
| pipefunc | ✅ | ❌ | ⚠️ | ⚠️ | ❌ | **2/5** |
| justpipe | ✅ | ❌ | ⚠️ | ❌ | ❌ | **2/5** |
| dynaflow | ✅ | ⚠️ | ❌ | ❌ | ❌ | **1/5** |
| dynapipeline | ✅ | ❌ | ❌ | ❌ | ❌ | **1/5** |
| pipeco | ⚠️ | ❌ | ❌ | ❌ | ❌ | **1/5** |

---

## Conclusion

**Ninguna librería implementada cumple los 5 objetivos.**

- **pypyr** y **pipelime** cumplen 3-4 objetivos pero no tienen el modelo de arquitectura de wx41.
- **Custom wx41** cumple la arquitectura pero faltan visualización y dry-run.

**Recomendacion:** Extender custom wx41 con:
1. YAML declarativo (como pypyr)
2. Visualizacion (como pipelime)
3. Dry-run (como pypyr/pipelime)
