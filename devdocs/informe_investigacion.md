# Informe de Investigación: Pipeline Libraries para wx41

Fecha: 2026-02-28

---

## Resumen Ejecutivo

Se investigaron 13 librerías de pipelines en Python para determinar la más adecuada para cumplir los 5 objetivos de wx41:

1. Encadenado de steps
2. Configuración declarativa
3. Visualización en UI
4. Resumability
5. Dry run

**Conclusión:** Ninguna librería cumple todos los objetivos. Se recomienda mantener la implementación custom + adoptar patrones pythonic de las librerías investigadas.

---

## Objetivos wx41 (plan_wx41.md)

| # | Objetivo | Descripcion |
|---|----------|-------------|
| 1 | Encadenado de steps | Capacidad de encadenar pasos en un pipeline |
| 2 | Configuración declarativa | Activation/desactivacion y configuracion de steps via YAML/JSON |
| 3 | Visualizacion en UI | Representacion grafica del pipeline |
| 4 | Resumability | Reanudar si se detiene |
| 5 | Dry run | Simular ejecucion sin ejecutar |

---

## Evaluacion Detallada vs plan_wx41.md

### Criterios de plan_wx41.md

| Criterio | Requisito | Evaluacion |
|----------|------------|------------|
| **PipelineContext** | `outputs: Dict[str, Path]` | Solo custom wx41 |
| **PipelineConfig** | `settings: Dict[str, Any]` | Custom + YAML libs |
| **StepConfig** | Dataclass propio por step | Solo custom wx41 |
| **output_keys** | En config, no hardcodeado | Solo custom wx41 |
| **Inmutabilidad** | `frozen=True` | Solo custom wx41 |
| **Busqueda por nombre** | `ctx.outputs.get("x")` | Solo custom wx41 |
| **Dinamismo** | Builder decide steps por settings | Solo custom wx41 |

---

## Ejemplos de Codigo por Libreria

### Custom wx41 (cumple todos los criterios de plan_wx41)

```python
# PipelineContext con outputs dict
@dataclass(frozen=True)
class PipelineContext:
    src: Path
    outputs: Dict[str, Path] = field(default_factory=dict)
    timings: Dict[str, float] = field(default_factory=dict)

# StepConfig con output_keys
@dataclass(frozen=True)
class TranscribeConfig:
    backend: str = "assemblyai"
    output_keys: Tuple[str, str] = ("transcript_txt", "transcript_json")

# Step busca input por nombre
def transcribe_step(ctx, config):
    audio = ctx.outputs.get("normalized") or ctx.src
    new_outputs = {**ctx.outputs, config.output_keys[0]: txt}
    return dataclasses.replace(ctx, outputs=new_outputs)
```

### pipefunc (DAG automatico)

```python
@pipefunc(output_name="transcript")
def transcribe(audio_path: Path) -> Path:
    ...

# DAG automatico por parametros
pipeline = Pipeline([normalize, transcribe])
result = pipeline("transcript", audio_path=src)
# NO hay PipelineContext, NO hay output_keys, NO hay inmutabilidad
```

### pypyr (YAML declarativo)

```yaml
# pipeline.yaml
steps:
  - name: wx41.normalize
    skip: false
  - name: wx41.transcribe
    skip: false
```

```python
# YAML a dict
context = {"audio_path": "audio.m4a"}
pipeline.run(context)
# NO hay PipelineContext, NO hay StepConfig, NO hay output_keys
```

### justpipe (State + eventos)

```python
@dataclass
class State:
    audio_path: Path = None
    transcript: Path = None

@pipe.step(to="transcribe")
def normalize(state):
    state.normalized = state.audio_path

pipe = Pipe()
# NO hay PipelineContext, NO hay StepConfig, NO hay inmutabilidad
```

---

## Tabla de Cumplimiento vs plan_wx41

| Criterio plan_wx41 | Custom | pipefunc | justpipe | pypyr | pipelime |
|--------------------|--------|----------|----------|-------|----------|
| outputs: Dict | ✅ | ❌ | ❌ | ❌ | ❌ |
| settings: Dict | ✅ | ❌ | ❌ | YAML | YAML |
| StepConfig dataclass | ✅ | ❌ | ❌ | ❌ | ❌ |
| output_keys en config | ✅ | ❌ | ❌ | ❌ | ❌ |
| frozen=True | ✅ | ❌ | ❌ | ❌ | ❌ |
| busca por nombre | ✅ | ❌ | ❌ | ❌ | ❌ |
| dinamico por settings | ✅ | ❌ | ❌ | YAML | YAML |

---

## Librerías Investigadas

### Implementadas con S1 (Walking Skeleton)

| # | Libreria | Score | Status |
|---|----------|-------|--------|
| 1 | pipefunc | 13 | Implementado |
| 2 | justpipe | 8 | Implementado |
| 3 | pypyr | 15 | Implementado |
| 4 | pipelime | 23 | Implementado |
| 5 | pipeco | 4 | Implementado |
| 6 | dynapipeline | 5 | Implementado |
| 7 | dynaflow | 9 | Implementado |
| 8 | **Custom wx41** | **14** | **Base** |

### No Implementadas

| # | Libreria | Razon |
|---|----------|-------|
| 9 | pydiverse.pipedag | Dependencias complejas |
| 10 | nextflow | Requiere Java |
| 11 | flyte | Overkill para el caso |
| 12 | snakemake | Workflow-focused |
| 13 | dagster | Overkill (score 25 pero muy pesado) |
| 14 | prefect | Overkill (score 25 pero muy pesado) |

---

## Tabla Comparativa

| Objetivo | Custom | pipefunc | justpipe | pypyr | pipelime | pipeco | dynapipeline | dynaflow |
|----------|--------|----------|----------|-------|----------|--------|--------------|----------|
| **Encadenado** | Si | Si | Si | Si | Si | Si | Si | Si |
| **Declarativo** | Si (dict) | No | No | YAML | YAML | No | No | JSON |
| **Visualizacion** | No | Si | Eventos | No | Si | No | No | No |
| **Resumability** | Si | Cache | No | No | Cache | No | No | No |
| **Dry run** | No | No | No | Si | Si | No | No | No |
| **StepConfig** | Si | No | No | No | No | Parcial | No | No |
| **Zero deps** | Si | No | Si | No | No | No | No | No |

---

## Scorecard (0-5 por objetivo)

| Libreria | Encadenado | Declarativo | Visualizacion | Resumability | Dry run | **Total** |
|----------|------------|-------------|---------------|--------------|---------|-----------|
| dagster | 5 | 5 | 5 | 5 | 5 | **25** |
| prefect | 5 | 5 | 5 | 5 | 5 | **25** |
| flyte | 5 | 5 | 5 | 5 | 5 | **25** |
| snakemake | 5 | 5 | 5 | 5 | 5 | **25** |
| pipelime | 5 | 5 | 4 | 4 | 5 | **23** |
| pypyr | 5 | 5 | 0 | 0 | 5 | **15** |
| **Custom wx41** | **5** | **4** | **0** | **5** | **0** | **14** |
| pipefunc | 5 | 0 | 4 | 4 | 0 | 13 |
| dynaflow | 5 | 4 | 0 | 0 | 0 | 9 |
| justpipe | 5 | 0 | 3 | 0 | 0 | 8 |
| dynapipeline | 5 | 0 | 0 | 0 | 0 | 5 |
| pipeco | 4 | 0 | 0 | 0 | 0 | 4 |

---

## Patrones Pythonic Captados

### 1. Definicion de Steps

| Patron | Libreria | Ejemplo |
|--------|----------|---------|
| Decoradores | pipefunc | `@pipefunc(output_name="x")` |
| Clases | pipeco, dynapipeline | `class MyStep(Step):` |
| Funciones | pypyr | `def my_step(context):` |
| YAML | pypyr | `steps: [{name: x}]` |

### 2. Configuracion

| Patron | Libreria | Ejemplo |
|--------|----------|---------|
| dataclasses | Custom wx41 | `@dataclass(frozen=True)` |
| Pydantic | pipeco | `class Config(BaseModel):` |
| YAML | pypyr, pipelime | `pipelines.yaml` |
| JSON | dynaflow | `{"StartAt": "x"}` |

### 3. State Management

| Patron | Libreria | Ejemplo |
|--------|----------|---------|
| Context | Custom wx41 | `PipelineContext` |
| State | justpipe | `@dataclass class State:` |
| Context | pypyr | `def step(context):` |
| Data dict | dynapipeline | `await stage.execute(data)` |

### 4. Encadenado

| Patron | Libreria | Ejemplo |
|--------|----------|---------|
| DAG automatico | pipefunc | Inferido por parametros |
| Pipes | pipeco | `Pipe(from=a, to=b)` |
| YAML flow | pypyr | `steps:` secuencial |
| Stage group | dynapipeline | `StageGroup(stages=[])` |

---

## Conclusion

### Por qué ninguna librería sirve tal cual

1. **Librerías completas (dagster, prefect, flyte)**: Cumplen todos los objetivos pero son overkill para wx41 - requieren infraestructura compleja, servidores, agentes, etc.

2. **Librerías ligeras (pipefunc, justpipe)**: Cumplen encadenado pero carecen de declarativo, resumability, dry-run.

3. **Librerías declarativas (pypyr, pipelime)**: Cumplen declarativo y dry-run pero no tienen el modelo de PipelineContext con outputs dict.

4. **Custom wx41**: Cumple arquitectura (StepConfig, output_keys, PipelineContext inmutable) pero carece de visualización y dry-run.

### Evaluacion vs Decisiones Tecnicas de plan_wx41

plan_wx41.md establece:

| Decision Tecnica | Requisito | Custom wx41 | pipefunc | pypyr |
|-----------------|------------|-------------|----------|-------|
| NamedStep generico | `fn: Callable[[Ctx], Ctx]` | ✅ | ❌ | ❌ |
| Context Setter | `output_fn` registra en outputs | ✅ | ❌ | ❌ |
| Inmutabilidad | `frozen=True` | ✅ | ❌ | ❌ |
| Step busca input por nombre | `ctx.outputs.get("x")` | ✅ | ❌ | ❌ |
| Step registra por nombre | `ctx.outputs["x"] = y` | ✅ | ❌ | ❌ |

### Recomendacion

**Mantener implementación custom** y adoptar patrones de las librerías:

| Objetivo | Como lograrlo |
|----------|---------------|
| Encadenado | Ya implementado (NamedStep) |
| Declarativo | Agregar YAML config para steps (sin cambiar core) |
| Visualizacion | Integrar graphviz o similar |
| Resumability | Ya implementado (check archivos existentes) |
| Dry run | Agregar flag de simulación |

### Siguiente paso

Implementar en wx41:
1. Soporte YAML para configuración declarativa de steps
2. Visualización con graphviz
3. Dry-run mode
