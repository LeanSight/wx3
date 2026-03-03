# Brechas: wx41.md vs plan_wx41.md vs Implementacion

Fecha: 2026-03-02

---

## BRECHA 4 — wx41.md: Cadena "Mejor Audio" incompleta en compress

**Donde**: `wx41.md` Seccion 4.2
**Doc dice**: fallback chain `enhanced > normalized > src`
**Codigo real** (`wx41/steps/compress.py:31`):
```python
audio = ctx.outputs.get("enhanced") or ctx.outputs.get("normalized")
```
No hay fallback a `src`. Si ambos son None, `audio=None` se pasa a `compress_video`.

**Impacto**: Doc describe comportamiento que no existe, o bien el codigo debe implementarlo.

---

## BRECHA 6 — wx41.md no menciona modulos existentes

Modulos en la implementacion no documentados en la arquitectura:
- `step_common.py` — decorador `timer` usado por `transcribe_step`
- `model_cache.py` — cache de modelo Whisper (`_get_model`, `_clear_model_cache`)
- `cli.py` — solo se menciona conceptualmente, sin listarlo como modulo del paquete

**Impacto en docs**: Agregar seccion de modulos de soporte en `wx41.md`.

---

## BRECHA 7 — MediaType: clase plana vs semantica de Enum

**Donde**: `wx41.md` Seccion 1.2
**Doc menciona** `MediaType` como tipo de deteccion de medio.
**Implementacion** (`wx41/wx4.py`): clase plana con constantes string, no un `Enum`.

**Impacto en docs**: Especificar en wx41.md que es una clase de constantes, no Enum.

---

## Resumen por prioridad

| # | Brecha | Estado | Donde corregir | Tipo | Impacto |
|---|--------|--------|----------------|------|---------|
| 1 | JSON state vs file-based Ctrl+C | ✅ RESUELTA | `wx41.md` + codigo | Contradiccion + refactor | **Critico** |
| 4 | "Mejor Audio" sin fallback a src | ✅ RESUELTA | `wx41.md` + codigo | Completado | **Alto** |
| 5 | update_ctx letra muerta | ✅ RESUELTA (via BRECHA 1) | - | Bug | **Alto** |
| 2 | pipeline.py → pipeline_engine.py | ✅ RESUELTA | `plan_wx41.md` | Nombre incorrecto | Medio |
| 3 | metadata-driven → disk-based | ✅ RESUELTA | `plan_wx41.md` | Descripcion incorrecta | Medio |
| 6 | Modulos no documentados | PENDIENTE | `wx41.md` | Omision | Bajo |
| 7 | MediaType clase vs Enum | PENDIENTE | `wx41.md` | Imprecision | Bajo |
