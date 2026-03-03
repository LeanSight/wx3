# Informe 3: Evaluacion Corregida vs 5 Objetivos wx41

Fecha: 2026-02-28

---

## Los 5 Objetivos wx41

1. **Encadenado de steps** - Capacidad de definir flujo de pasos
2. **Configuracion declarativa** - Activation/desactivacion via codigo, dict, YAML, JSON, decoradores
3. **Visualizacion en UI** - Representacion grafica del pipeline
4. **Resumability** - Reanudar si se detiene
5. **Dry run** - Simular ejecucion sin ejecutar

**Nota:** Declarativo NO es solo YAML/JSON. Se puede hacer via Python (decoradores, clases, dicts).

---

## pipefunc

### Score: 3/5

| Objetivo | Cumple | Justificacion |
|----------|--------|---------------|
| Encadenado | ✅ Si | `@pipefunc(output_name="x")` + DAG automatico |
| Declarativo | ✅ Si | Decoradores Python declaran outputs: `@pipefunc(output_name="x")` |
| Visualizacion | ⚠️ Parcial | `pipeline.visualize()` genera grafico |
| Resumability | ⚠️ Parcial | Cache automatico |
| Dry run | ❌ No | No tiene modo simulacion |

### Codigo

```python
# Declarativo via decorador Python
@pipefunc(output_name="transcript")
def transcribe(audio: Path) -> Path:
    return audio

# Encadenado automatico por parametros
pipeline = Pipeline([normalize, transcribe])
```

---

## justpipe

### Score: 2/5

| Objetivo | Cumple | Justificacion |
|----------|--------|---------------|
| Encadenado | ✅ Si | `@pipe.step(to="x")` declara flujo |
| Declarativo | ✅ Si | Decoradores declaran steps y flujo |
| Visualizacion | ⚠️ Parcial | Eventos para UI externa |
| Resumability | ❌ No | No tiene cache |
| Dry run | ❌ No | No tiene modo simulacion |

### Codigo

```python
# Declarativo via decorador
@pipe.step(to="transcribe")
def normalize(state):
    state.normalized = state.audio_path
```

---

## pypyr

### Score: 4/5

| Objetivo | Cumple | Justificacion |
|----------|--------|---------------|
| Encadenado | ✅ Si | Steps secuenciales en YAML |
| Declarativo | ✅ Si | YAML nativo |
| Visualizacion | ❌ No | No tiene |
| Resumability | ❌ No | No tiene |
| Dry run | ✅ Si | `pypyr --dry-run` |

---

## pipelime

### Score: 4/5

| Objetivo | Cumple | Justificacion |
|----------|--------|---------------|
| Encadenado | ✅ Si | `Piper() << Stage()` |
| Declarativo | ✅ Si | YAML/JSON + Python API |
| Visualizacion | ✅ Si | UI integrada |
| Resumability | ⚠️ Parcial | Cache |
| Dry run | ✅ Si | `--dry-run` |

---

## pipeco

### Score: 2/5

| Objetivo | Cumple | Justificacion |
|----------|--------|---------------|
| Encadenado | ✅ Si | Pipes declaran flujo |
| Declarativo | ✅ Si | Clases Python declaran inputs/outputs |
| Visualizacion | ❌ No | No tiene |
| Resumability | ❌ No | No tiene |
| Dry run | ❌ No | No tiene |

### Codigo

```python
# Declarativo via clases Python
class TranscribeStep(Step):
    audio_in: Path  # Declara input
    transcript: Path  # Declara output
```

---

## dynapipeline

### Score: 2/5

| Objetivo | Cumple | Justificacion |
|----------|--------|---------------|
| Encadenado | ✅ Si | StageGroup + ExecutionStrategy |
| Declarativo | ✅ Si | Clases Python declaran stages |
| Visualizacion | ❌ No | No tiene |
| Resumability | ❌ No | No tiene |
| Dry run | ❌ No | No tiene |

---

## dynaflow

### Score: 2/5

| Objetivo | Cumple | Justificacion |
|----------|--------|---------------|
| Encadenado | ✅ Si | JSON/ASL define flujo |
| Declarativo | ✅ Si | JSON declara states y transiciones |
| Visualizacion | ❌ No | No tiene |
| Resumability | ❌ No | No tiene |
| Dry run | ❌ No | No tiene |

---

## Custom wx41 (Base)

### Score: 3/5

| Objetivo | Cumple | Justificacion |
|----------|--------|---------------|
| Encadenado | ✅ Si | NamedStep + Pipeline.run() |
| Declarativo | ✅ Si | `settings: Dict[str, Any]` + dataclasses |
| Visualizacion | ❌ No | No tiene |
| Resumability | ✅ Si | Check archivos existentes |
| Dry run | ❌ No | No tiene |

### Codigo

```python
# Declarativo via dict y dataclasses
config = PipelineConfig(
    settings={"transcribe": TranscribeConfig(backend="whisper")}
)
```

---

## Tabla Resumen Corregida

| Libreria | Encadenado | Declarativo | Visualizacion | Resumability | Dry run | Total |
|----------|------------|-------------|---------------|--------------|---------|-------|
| pipelime | ✅ | ✅ | ✅ | ⚠️ | ✅ | **4/5** |
| pypyr | ✅ | ✅ | ❌ | ❌ | ✅ | **3/5** |
| Custom wx41 | ✅ | ✅ | ❌ | ✅ | ❌ | **3/5** |
| pipefunc | ✅ | ✅ | ⚠️ | ⚠️ | ❌ | **3/5** |
| justpipe | ✅ | ✅ | ⚠️ | ❌ | ❌ | **2/5** |
| pipeco | ✅ | ✅ | ❌ | ❌ | ❌ | **2/5** |
| dynapipeline | ✅ | ✅ | ❌ | ❌ | ❌ | **2/5** |
| dynaflow | ✅ | ✅ | ❌ | ❌ | ❌ | **2/5** |

---

## Conclusion

**Correciones aplicadas:**

- **Declarativo** ahora se evalua como: cualquier forma de declarar configuracion (Python decorators, classes, dicts, YAML, JSON)
- 7/8 librerías ahora cumplen "declarativo" (solo pypyr usa YAML, las demas usan Python)
- pipelime sigue siendo la mejor (4/5)
- Custom wx41 y pipefunc empatan en 3/5

**Recomendacion inalterada:** Extender custom wx41 con visualizacion y dry-run.
