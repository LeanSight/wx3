# Diagnostico: Gaps en tests de steps del pipeline

Fecha: 2026-03-06

## Contexto

Al eliminar la logica duplicada de skip en `normalize_step` y `enhance_step` (que repitian
el chequeo de `cache_hit` / `out.exists()` que ya hace la pipeline), se expusieron varios
problemas latentes en los tests. Este documento cataloga todos los gaps encontrados en
`wx4/tests/test_steps.py`.

---

## Problemas ya corregidos

### BRECHA-1: Early return por `cache_hit` duplicado en `normalize_step`

**Archivo:** `wx4/steps/normalize.py:28`

**Problema:** `normalize_step` tenia:
```python
if ctx.cache_hit or out.exists():
    return ...  # skip silencioso
```
La pipeline ya salta el step si `out.exists()`. El `cache_hit` causaba skip aunque el
archivo no existiera, dejando `ctx.normalized = None` silenciosamente.

**Fix aplicado:** Early return eliminado. La pipeline es la unica fuente de verdad para skip.

**Tests eliminados:**
- `TestNormalizeStep::test_skips_when_cache_hit`
- `TestNormalizeStep::test_skips_on_cache_hit`

---

### BRECHA-2: Early return por `cache_hit` duplicado en `enhance_step`

**Archivo:** `wx4/steps/enhance.py:31`

**Problema:** identico al anterior.

**Fix aplicado:** Early return eliminado.

**Tests eliminados:**
- `TestEnhanceStep::test_returns_cached_path_on_hit`

---

### BRECHA-3: Patch path incorrecto en tests de `normalize_step`

**Archivo:** `wx4/tests/test_steps.py` - `TestNormalizeStep`

**Problema:** Tres tests patcheaban `wx4.steps.enhance.to_aac` en vez de
`wx4.steps.normalize.to_aac`. La referencia importada en `normalize.py` es independiente
de la de `enhance.py`. El mock era silenciosamente inefectivo; los tests pasaban porque la
funcion real `to_aac` era llamada en la mayoria de los casos sin error visible.

**Tests corregidos** (patch path cambiado a `wx4.steps.normalize.to_aac`):
- `TestNormalizeStep::test_calls_extract_normalize_encode`
- `TestNormalizeStep::test_does_not_call_apply_clearvoice`
- `TestNormalizeStep::test_timing_recorded`

---

### BRECHA-4: `TestEnhanceStep::test_timing_recorded` usaba `cache_hit=True` como shortcut

**Problema:** El test seteaba `cache_hit=True` para forzar el early return (ya eliminado)
y simplemente verificar que `"enhance"` apareciera en `timings`. Al eliminar el early
return, el test intentaba correr ClearVoice sobre un archivo fake y fallaba.

**Fix aplicado:** Reescrito con mocks de `apply_clearvoice` y `to_aac`.

---

## Problemas latentes encontrados (pendientes de correccion)

### GAP-1: Patch path incorrecto en `TestCacheSaveStep`

**Archivo:** `wx4/tests/test_steps.py:91,125`

**Problema:** Dos tests patchean `wx4.steps.file_key` pero `file_key` no esta exportado
en `wx4/steps/__init__.py`. La funcion real es `wx4.steps.cache_save.file_key`.

```python
# Incorrecto:
patch("wx4.steps.file_key", return_value="fake-key")

# Correcto:
patch("wx4.steps.cache_save.file_key", return_value="fake-key")
```

**Por que pasa igual:** La funcion real `file_key` opera sobre `b"fake audio"` sin error.
El mock es silenciosamente inefectivo — `save_cache` es mockeado, por lo que no hay
escritura a disco y el test no detecta la diferencia.

**Severidad:** LATENTE. Si `file_key` alguna vez falla sobre datos invalidos, estos tests
empezarian a fallar de forma confusa.

**Tests afectados:**
- `TestCacheSaveStep::test_saves_when_enhanced_and_no_hit`
- `TestCacheSaveStep::test_timing_recorded`

---

### GAP-2: Patches muertos de normalize en tests de `enhance_step`

**Archivo:** `wx4/tests/test_steps.py` - multiples clases

**Problema:** Cinco tests que llaman `enhance_step` incluyen patches de funciones de
`normalize_step` (`extract_to_wav`, `normalize_lufs`) que `enhance_step` nunca llama.
Son patches completamente muertos que no interceptan nada.

```python
# Estos patches no tienen efecto en enhance_step:
patch("wx4.steps.normalize.extract_to_wav", return_value=True),
patch("wx4.steps.normalize.normalize_lufs"),
```

**Locations:**
- `TestEnhanceStepAtomicity::test_tmp_files_removed_after_success` (lineas 383-384)
- `TestEnhanceStepAtomicity::test_cleanup_runs_even_if_encode_fails` (lineas 418-419)
- `TestEnhanceStepAtomicity::test_final_output_not_written_when_encode_fails` (lineas 439-440)
- `TestEnhanceStepPassesStepProgress::test_step_progress_forwarded_to_apply_clearvoice` (lineas 893-894)
- `TestEnhanceStepPassesStepProgress::test_step_progress_none_when_not_set` (lineas 913-914)

**Severidad:** RUIDO. No causan fallos pero oscurecen la intencion del test y dan falsa
seguridad de que normalize esta siendo testeado.

---

### GAP-3: Assertions vacuas en `TestEnhanceStepAtomicity::test_cleanup_runs_even_if_encode_fails`

**Archivo:** `wx4/tests/test_steps.py:397-431`

**Problema:** El test crea las variables `tmp_raw` y `tmp_norm` como objetos `Path` sin
escribirlos a disco, y luego afirma que no existen. Como `enhance_step` nunca crea esos
archivos (son responsabilidad de `normalize_step`), las assertions son trivialmente
verdaderas independientemente del comportamiento de enhance.

```python
assert not tmp_raw.exists()   # vacuamente verdadero: enhance nunca crea tmp_raw
assert not tmp_norm.exists()  # vacuamente verdadero: enhance nunca crea tmp_norm
assert not tmp_enh.exists()   # correcta: enhance si crea y debe limpiar tmp_enh
```

**Severidad:** FALSA SEGURIDAD. El test da la impresion de verificar limpieza de normalize,
pero no lo hace. Solo `tmp_enh` esta realmente siendo verificado.

---

### GAP-4: Patch path incorrecto en `TestCompressStep` (skip por RuntimeError)

**Archivo:** `wx4/tests/test_steps.py:750-768`

**Problema:** Dos tests patchean `wx4.steps.video.probe_video` pero `compress_step`
importa `probe_video` en su propio modulo (`wx4.steps.compress.probe_video`).

```python
# Incorrecto:
patch("wx4.steps.video.probe_video", side_effect=RuntimeError("no video stream"))

# Correcto:
patch("wx4.steps.compress.probe_video", side_effect=RuntimeError("no video stream"))
```

**Por que pasan igual:** El mock no intercepta la llamada real. La funcion real `probe_video`
es llamada sobre `tmp_path / "audio.mp3"` que contiene `b"fake audio"`, lo que genera un
`RuntimeError` real. `compress_step` captura ese error y retorna early — el mismo
comportamiento que el test intenta simular, pero por coincidencia, no por el mock.

**Tests afectados:**
- `TestCompressStep::test_skips_silently_when_source_has_no_video_stream`
- `TestCompressStep::test_timing_recorded_on_audio_only_skip`

**Severidad:** LATENTE. Si `probe_video` dejara de fallar sobre datos invalidos (por
ejemplo, si se agrega fallback o validacion previa), estos tests dejarian de testear el
comportamiento de skip y pasarian igualmente sin detectar la regresion.

---

## Resumen

| ID | Tipo | Severidad | Estado |
|----|------|-----------|--------|
| BRECHA-1 | Early return duplicado en normalize_step | CRITICO | Corregido |
| BRECHA-2 | Early return duplicado en enhance_step | CRITICO | Corregido |
| BRECHA-3 | Patch path incorrecto en tests de normalize | MEDIO | Corregido |
| BRECHA-4 | test_timing_recorded usaba cache_hit shortcut | BAJO | Corregido |
| GAP-1 | `wx4.steps.file_key` no existe, mock inefectivo | LATENTE | Pendiente |
| GAP-2 | Patches muertos de normalize en tests de enhance | RUIDO | Pendiente |
| GAP-3 | Assertions vacuas en test de atomicidad | FALSA SEGURIDAD | Pendiente |
| GAP-4 | `wx4.steps.video.probe_video` en tests de compress | LATENTE | Pendiente |

## Patron comun

Todos los gaps responden al mismo patron: **el patch path apunta al modulo equivocado**.
En Python, `patch("modulo_A.fn")` solo intercepta llamadas que usan la referencia importada
en `modulo_A`. Si `modulo_B` importa `fn` directamente con `from X import fn`, hay que
patchear `modulo_B.fn`. Este error es silencioso cuando la funcion real no falla.
