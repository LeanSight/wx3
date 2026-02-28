# Plan: Reorganizar steps en subcarpeta wx4/steps/

## Objetivo
Separar cada step de `wx4/steps.py` en su propio archivo dentro de `wx4/steps/`.

---

## Slice 1: Crear estructura base

**Test** (test_acceptance.py):
```python
def test_steps_importable_from_package(self):
    from wx4.steps import cache_check_step, normalize_step, enhance_step
```

**Producción**:
- Crear `wx4/steps/__init__.py` que re-exporte desde `wx4.steps`

---

## Slice 2: Mover cache_check_step

**Test** (test_steps.py):
```python
def test_cache_check_step_importable(self):
    from wx4.steps.cache_check import cache_check_step
```

**Producción**:
- Crear `wx4/steps/cache_check.py` con la función
- Actualizar `wx4/steps/__init__.py`

---

## Slice 3: Mover normalize_step

**Test** (test_steps.py):
```python
def test_normalize_step_importable(self):
    from wx4.steps.normalize import normalize_step
```

**Producción**:
- Crear `wx4/steps/normalize.py`
- Actualizar `wx4/steps/__init__.py`

---

## Slice 4: Mover enhance_step

**Test** (test_steps.py):
```python
def test_enhance_step_importable(self):
    from wx4.steps.enhance import enhance_step
```

**Producción**:
- Crear `wx4/steps/enhance.py` (incluye `_load_clearvoice`)

---

## Slice 5: Mover cache_save_step

**Test**:
```python
def test_cache_save_step_importable(self):
    from wx4.steps.cache_save import cache_save_step
```

---

## Slice 6: Mover transcribe_step

**Test**:
```python
def test_transcribe_step_importable(self):
    from wx4.steps.transcribe import transcribe_step
```

---

## Slice 7: Mover srt_step

**Test**:
```python
def test_srt_step_importable(self):
    from wx4.steps.srt import srt_step
```

---

## Slice 8: Mover video_step

**Test**:
```python
def test_video_step_importable(self):
    from wx4.steps.video import video_step
```

**Producción**:
- Crear `wx4/steps/video.py` (incluye `_compress_video_from_audio`)

---

## Slice 9: Mover compress_step

**Test**:
```python
def test_compress_step_importable(self):
    from wx4.steps.compress import compress_step
```

---

## Slice 10: Actualizar pipeline.py

**Test** (test_pipeline.py):
- Verificar que pipeline funcione con nuevos imports

**Producción**:
- Actualizar imports en `pipeline.py`

---

## Slice 11: Tests de integración

**Test** (test_acceptance.py):
- Ejecutar pipeline completo
- Verificar que todo funciona end-to-end

---

## Resumen

| Slice | Step | Archivo |
|-------|------|---------|
| 1 | Estructura | steps/__init__.py |
| 2 | cache_check | steps/cache_check.py |
| 3 | normalize | steps/normalize.py |
| 4 | enhance | steps/enhance.py |
| 5 | cache_save | steps/cache_save.py |
| 6 | transcribe | steps/transcribe.py |
| 7 | srt | steps/srt.py |
| 8 | video | steps/video.py |
| 9 | compress | steps/compress.py |
| 10 | Pipeline | pipeline.py |
| 11 | Integración | test_acceptance.py |

## Archivos a eliminar al final
- `wx4/steps.py`
