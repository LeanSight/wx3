# Comparacion: Implementaciones wx41 contra objetivos de plan_wx41.md

## Tabla Comparativa

| Objetivo (plan_wx41.md) | Custom (wx41/) | pipefunc (wx41_pipefunc/) | pipeco (wx41_pipeco/) |
|-------------------------|----------------|---------------------------|----------------------|
| **PipelineContext** con `outputs: Dict[str, Path]` | Si (nativo) | No - parametros sueltos | No - atributos de clase |
| **PipelineConfig** con `settings: Dict` (bolsa de StepConfigs) | Si (nativo) | No - parametros por funcion | Parcial - en Step.define() |
| **StepConfig** propio por step | Si - TranscribeConfig | No - parametros sueltos | Parcial - atributos clase |
| Step busca input por nombre en `ctx.outputs` | Si | No | No |
| Step registra outputs en `ctx.outputs` por nombre | Si | No | No |
| **Inmutabilidad** (frozen=True) | Si | No | No |
| **NamedStep** generico `fn: Callable[[Ctx], Ctx]` | Si | No | No |
| **Context Setter** generico (output_fn) | Si | No | No |
| **Dinamismo**: builder mira settings para añadir steps | Si | No | No |
| **Observers** para lifecycle events | Si | No | No |
| **Resume/Skip** (archivos ya existen) | Soportado | Cache auto | No |
| **Zero dependencies** | Si | pipefunc | pipeco+pydantic |
| **Cero I/O en ctx** (solo Path) | Si | No | No |

---

## Detalle por Implementacion

### 1. Custom (wx41/)

Cumple todos los objetivos nativamente.

```python
@dataclass(frozen=True)
class PipelineContext:
    src: Path
    outputs: Dict[str, Path] = field(default_factory=dict)

@dataclass(frozen=True)
class TranscribeConfig:
    output_keys: Tuple[str, str] = ("transcript_txt", "transcript_json")

def transcribe_step(ctx, config):
    audio = ctx.outputs.get("normalized") or ctx.src
    txt, jsn = ...
    new_outputs = {**ctx.outputs, config.output_keys[0]: txt}
    return dataclasses.replace(ctx, outputs=new_outputs)
```

### 2. pipefunc (wx41_pipefunc/)

NO cumple objetivos - enfoque diferente.

```python
@pipefunc(output_name="normalized")
def normalize(audio_path: Path) -> Path:
    return audio_path

# El pipeline pasa parametros directamente, NO hay ctx.outputs
pipeline = Pipeline([normalize, transcribe])
result = pipeline("json", audio_path=src)
```

**Problemas**: Sin PipelineContext, sin outputs dict, sin observers, sin resume/skip control.

### 3. pipeco (wx41_pipeco/)

Parcialmente cumple - enfoque OOP diferente.

```python
class TranscribeStep(Step):
    audio_in: Path  # No es ctx.outputs
    transcript_txt: Path  # No se registra en dict

    def run(self):
        self.transcript_txt = txt  # Asigna a atributo
```

**Problemas**: Sin ctx.outputs, sin inmutabilidad, sin observers, muy nuevo (0.1.3).

---

## Conclusion

| Criterio | Custom | pipefunc | pipeco |
|----------|--------|----------|--------|
| **Cumple objetivos plan_wx41** | **Si (100%)** | No (20%) | Parcial (40%) |
| Dependencies | 0 | 1 | 2 |
| Madurez | N/A | Alta (452 stars) | Baja (nuevo) |

**Recommendation**: Mantener implementacion custom. Las librerias no cumplen los objetivos de arquitectura de wx41.