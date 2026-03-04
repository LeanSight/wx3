# BRECHA: Eliminar cache_check, cache_save y cache_io

## Problema

El cache son los archivos en disco. `Pipeline.run()` ya implementa resumabilidad via `out.exists() + ctx_setter` en cada `NamedStep`. `cache_check` y `cache_save` son capas redundantes sobre eso.

El JSON cache (`cache_io.py`) es estado extra que puede desincronizarse con el disco.

## Estado: PENDIENTE

---

## Slice 1: build_steps() no contiene cache steps

**AT en RED** - reemplazar `test_default_has_cache_check_enhance_cache_save_transcribe_srt`:

```python
def test_default_has_no_cache_steps():
    from wx4.pipeline import build_steps
    from wx4.steps import cache_check_step, cache_save_step

    fns = self._fns(build_steps())
    assert cache_check_step not in fns, "cache_check_step should not be in build_steps()"
    assert cache_save_step not in fns, "cache_save_step should not be in build_steps()"
```

RED esperado: `AssertionError: cache_check_step should not be in build_steps()`

**GREEN**: eliminar `cache_check` y `cache_save` de `build_steps()` en `pipeline.py`.

**Commit**: `Remove cache_check and cache_save from build_steps()`

---

## Slice 2: Pipeline.run() no tiene tratamiento especial de cache_check

**AT en RED**:

```python
def test_pipeline_run_has_no_cache_check_special_case():
    import inspect
    from wx4.pipeline import Pipeline
    src = inspect.getsource(Pipeline.run)
    assert "cache_check" not in src, (
        "Pipeline.run() should not have special-case logic for cache_check"
    )
```

RED esperado: `AssertionError: Pipeline.run() should not have special-case logic for cache_check`

**GREEN**: eliminar el bloque especial de `cache_check_step_fn` en `Pipeline.run()` (lineas 69-78) y en `Pipeline.dry_run()` (lineas 117-126).

**Commit**: `Remove cache_check special-case from Pipeline.run() and dry_run()`

---

## Slice 3: PipelineContext no tiene campos cache

**Unit test en RED**:

```python
def test_pipeline_context_has_no_cache_fields():
    from wx4.context import PipelineContext
    from pathlib import Path
    ctx = PipelineContext(src=Path("/tmp/audio.m4a"))
    assert not hasattr(ctx, "cache_hit"), "cache_hit should not exist on PipelineContext"
    assert not hasattr(ctx, "cache"), "cache should not exist on PipelineContext"
```

RED esperado: `AssertionError: cache_hit should not exist on PipelineContext`

**GREEN**: eliminar `cache_hit` y `cache` de `PipelineContext` en `context.py`.

**Commit**: `Remove cache_hit and cache fields from PipelineContext`

---

## Slice 4: Eliminar archivos muertos

Con los 3 slices anteriores en GREEN, estos archivos ya no tienen referencias.

**AT de cierre**:

```python
def test_cache_modules_do_not_exist():
    import importlib
    for mod in ["wx4.steps.cache_check", "wx4.steps.cache_save", "wx4.cache_io"]:
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module(mod)
```

**GREEN**: eliminar archivos y limpiar imports.

Archivos a eliminar:
- `wx4/steps/cache_check.py`
- `wx4/steps/cache_save.py`
- `wx4/cache_io.py`

Archivos a editar:
- `wx4/steps/__init__.py` - eliminar imports de `cache_check_step` y `cache_save_step`

**Commit**: `Delete cache_check, cache_save, cache_io modules`

---

## Tests existentes afectados

| Test | Cambio |
|------|--------|
| `test_default_has_cache_check_enhance_cache_save_transcribe_srt` | Reemplazar por `test_default_has_no_cache_steps` (Slice 1) |
| `test_skip_enhance_removes_cache_and_enhance_steps` | Eliminar referencias a `cache_check_step`/`cache_save_step` |
| `test_all_flags_combined` | Idem |
| `test_step_without_output_fn_never_skipped` | Renombrar step de ejemplo (usa nombre "cache_check") |
| `test_dry_run_no_output_fn_always_runs` | Idem |

---

## Orden de archivos por slice

```
Slice 1: wx4/tests/test_pipeline.py  wx4/pipeline.py (build_steps)
Slice 2: wx4/tests/test_pipeline.py  wx4/pipeline.py (Pipeline.run, dry_run)
Slice 3: wx4/tests/test_context.py   wx4/context.py (PipelineContext)
Slice 4: wx4/steps/__init__.py, wx4/steps/cache_check.py,
         wx4/steps/cache_save.py, wx4/cache_io.py
```
