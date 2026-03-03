# plan_wx41.md - Implementación ATDD/TDD Modular

Fecha: 2026-03-02
Ref: devdocs/standard-atdd-tdd.md, devdocs/arquitectura.md, devdocs/meta_at_design.md

---

## Estado de Implementación (FINAL)

| Objetivo | Estado | Archivos |
|----------|--------|----------|
| Encadenado de steps | ✅ IMPLEMENTADO | pipeline_engine.py |
| Configuración declarativa dinámica | ✅ IMPLEMENTADO | steps/__init__.py (STEP_REGISTRY) |
| Visualización UI | ✅ IMPLEMENTADO | ui/progress.py |
| Resumability (disk-based) | ✅ IMPLEMENTADO | pipeline_engine.py |
| Dry run | ✅ IMPLEMENTADO | pipeline_engine.py, context.py |
| Ctrl+C cleanup | ✅ IMPLEMENTADO | pipeline_engine.py (auto-cleanup on interrupt) |
| CLI Agnóstico (Auto-discovery) | ✅ IMPLEMENTADO | cli.py |
| StepInfo Registry unificado | ✅ IMPLEMENTADO | steps/__init__.py |
| Meta-AT Registry-Driven | ✅ IMPLEMENTADO | tests/test_acceptance.py |

### Tests
```
pytest wx41/tests/ -v
43 passed
```

---

## 3. Tabla de Registro de Steps

| Step | Nombre Output en `ctx.outputs` | Dependencia (Input) | Estado |
|------|-------------------------------|---------------------|--------|
| `normalize` | `"normalized"` | `ctx.src` | ✅ IMPLEMENTADO |
| `enhance` | `"enhanced"` | `"normalized"` o `ctx.src` | ✅ IMPLEMENTADO |
| `transcribe` | `"transcript_txt/json"`| `"enhanced"` o `"normalized"` o `ctx.src` | ✅ IMPLEMENTADO |
| `srt` | `"srt"` | `"transcript_json"` | ✅ IMPLEMENTADO |
| `black_video`| `"video"` | Cualquiera de audio anterior | ✅ IMPLEMENTADO |
| `compress` | `"video_compressed"` | `"video"` | ✅ IMPLEMENTADO |

---

## 4. Arquitectura Final (2026 Idiomatic Python)

1. **Auto-Discovery**: `steps/__init__.py` utiliza `pkgutil` para cargar dinámicamente los submódulos. Agregar un archivo en `steps/` registra automáticamente el step.
2. **Dynamic CLI**: Basado en `click`. Inspecciona los campos de cada `StepConfig` (dataclass) para generar flags `--{step}-{field}` y `--no-{step}`.
3. **Path Oracle**: `predict_output_path` centraliza la convención de nombres, asegurando que tests y producción hablen el mismo lenguaje.
4. **Meta-AT**: Los tests de aceptación son dinámicos. Pytest se parametriza con el Registro, garantizando que CUALQUIER nuevo step cumpla con el contrato de Chaining, CLI, Resumability y Dry-run sin escribir tests nuevos.
5. **Dependency Injection**: Uso de `functools.partial` para inyectar configuraciones en el pipeline de forma limpia y transparente.
