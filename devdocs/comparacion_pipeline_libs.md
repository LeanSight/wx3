# Comparacion: Implementaciones S1 vs Objetivos wx41

## Objetivos wx41 (plan_wx41.md)

1. Forma mas idiomática y pythónica en 2026
2. Encadenado de steps
3. Activación/desactivación y configuración declarativa de steps
4. Visualización en una UI
5. Resumability (retoma si se detiene)
6. Dry run (simular ejecución)

---

## Tabla Comparativa

| Objetivo | Custom (wx41/) | pipefunc | justpipe | pypyr | pipelime |
|----------|----------------|----------|----------|-------|----------|
| **Encadenado de steps** | Si | Si (DAG) | Si | Si | Si |
| **Configuración declarativa** | Si (settings dict) | No | No | **Si (YAML)** | **Si (YAML)** |
| **Visualización UI** | No | Si | Si (eventos) | No | Si |
| **Resumability** | Si | Cache auto | No | No | Cache |
| **Dry run** | No | No | No | **Si** | **Si** |
| **Zero dependencies** | Si | pipefunc | justpipe | pypyr+deps | pipelime+deps |
| **Async** | No | Opcional | Si | No | No |
| **StepConfig propio** | Si | No | No | No | No |
| **output_keys en config** | Si | No | No | No | No |
| **PipelineContext** | Si | No | State | Context | No |
| **Inmutable** | Si | No | No | No | No |

---

## Detalle por Libreria

### 1. Custom (wx41/)

**Pros:**
- Cumple todos los objetivos de arquitectura
- Zero dependencies
- StepConfig con output_keys
- PipelineContext inmutable
- Resumability implementado

**Cons:**
- Sin visualización
- Sin dry run
- Mantenimiento manual

### 2. pipefunc (wx41_pipefunc/)

```python
@pipefunc(output_name="transcript")
def transcribe(audio_path: Path) -> Path:
    ...

pipeline = Pipeline([transcribe])
result = pipeline("transcript", audio_path=src)
```

**Pros:**
- DAG automático
- Visualización integrada
- Map-reduce
- 452 stars

**Cons:**
- Sin PipelineContext
- Sin configuración declarativa
- Sin dry run

### 3. justpipe (wx41_justpipe/)

```python
@pipe.step(to="transcribe")
def normalize(state):
    ...

pipe = Pipe()
```

**Pros:**
- Zero dependencies
- Async-first
- Eventos para UI
- Moderno (Ene 2026)

**Cons:**
- Sin configuración declarativa
- Sin resumability
- Sin dry run

### 4. pypyr (wx41_pypyr/)

```yaml
steps:
  - name: wx41.steps.normalize
  - name: wx41.steps.transcribe
```

**Pros:**
- **Configuración declarativa YAML**
- **Dry run nativo**
- Conditional execution
- Loop support

**Cons:**
- Muchas dependencias
- Paradigma diferente (CLI-oriented)
- Sin PipelineContext

### 5. pipelime (wx41_pipelime/)

```python
piper = Piper()
piper << NormalizeStage()
piper << TranscribeStage()
```

**Pros:**
- **Configuración declarativa YAML/JSON**
- **Dry run**
- **Visualización**
- Caching

**Cons:**
- Muchas dependencias
- Paradigma data-focused
- Sin PipelineContext

---

## Conclusion

| Criterio | Custom | pipefunc | justpipe | pypyr | pipelime |
|----------|--------|----------|----------|-------|----------|
| **Adecuado para wx41** | **Si** | Parcial | Parcial | Parcial | Parcial |
| **Cumple objetivos plan** | 3/6 | 2/6 | 2/6 | 3/6 | 4/6 |
| **Recomendado** | **Si** | No | No | No | No |

**Ninguna librería cumple todos los objetivos de wx41.** La implementación custom es la única que:
- Tiene StepConfig propio con output_keys
- Usa PipelineContext con outputs dict
- Es inmutable
- Soporta resumability

Las librerías externas cumplen objetivos parciales pero no el modelo de arquitectura de wx41.

**Siguiente paso:** Investigar cómo implementar visualización y dry-run en la solución custom.
