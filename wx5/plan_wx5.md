# wx5/plan_wx5.md - Walking Skeleton SLICE 1

Fecha: 2026-03-04

## Objetivo: Walking Skeleton

Crear estructura mínima que cruce todas las capas y tenga un smoke test pasando.

## Objetivos wx5 (heredados de wx41)

| Objetivo | Descripción |
|----------|-------------|
| Encadenado de steps | Output de un step es input del siguiente |
| Configuración declarativa | Python declarativo estilo lxml E-factory |
| Resumability | Retomar si se detiene |
| Dry run | Simular ejecución |
| CLI auto-configurable | Flags desde parámetros de steps |
| Pipeline como fuente | Pipeline.register() es la fuente de verdad |

## Arquitectura SLICE 1

```
wx5/
├── wx5/
│   └── __init__.py   # Engine mínimo: Pipeline, P, run_pipeline
├── tests/
│   └── test_acceptance.py
```

## SLICE 1: Walking Skeleton

### Comportamiento esperado

1. `Pipeline.register(name, output_keys, optional)` - registra step
2. `Pipeline.get_step(name)` - consulta step registrado
3. `Pipeline.get_all_steps()` - retorna todos los steps
4. `P.audio("step1", "step2")` - define pipeline
5. `run_pipeline(pipeline, src)` - ejecuta y retorna contexto con outputs

### Test smoke

```python
def test_walking_skeleton():
    Pipeline.register("normalize", output_keys=("normalized",))
    pipeline = P.audio("normalize")
    result = run_pipeline(pipeline, src=Path("test.mp3"))
    assert result.src == Path("test.mp3")
    assert "normalized" in result.outputs
```

## Decisiones de diseño

- Pipeline es el objeto consultable (no existe registry separado)
- Registro via `Pipeline.register()` como clase variable
- PipelineDef solo contiene nombres de steps
- Engine hardcodeado por ahora (sin lógica real)
