# nullable_vs_mocks.md - Nullables vs Mocks en wx41

## El caso concreto: normalize_step en wx41

El step wx41 quedara asi (simplificado):

```python
# wx41/steps/normalize.py
from wx41.step_common import timer, atomic_output, temp_files
from wx41.audio_extract import extract_to_wav
from wx41.audio_normalize import normalize_lufs
from wx41.audio_encode import to_aac

@timer("normalize")
def normalize_step(ctx):
    out = ctx.src.parent / f"{ctx.src.stem}_normalized.m4a"
    tmp_raw = ctx.src.parent / f"{ctx.src.stem}._tmp_raw.wav"
    tmp_norm = ctx.src.parent / f"{ctx.src.stem}._tmp_norm.wav"

    with temp_files(tmp_raw, tmp_norm):
        if not extract_to_wav(ctx.src, tmp_raw):
            raise RuntimeError(f"extract_to_wav failed for {ctx.src.name}")
        normalize_lufs(tmp_raw, tmp_norm)
        with atomic_output(out) as tmp_out:
            if not to_aac(tmp_norm, tmp_out):
                raise RuntimeError(f"to_aac failed for {ctx.src.name}")

    return dataclasses.replace(ctx, normalized=out)
```

---

## Por que NO mockear step_common

`@timer`, `atomic_output`, `temp_files` son funciones que trabajan **solo con `Path` y `time`**.
No necesitan FFmpeg, no llaman a APIs externas. Funcionan en tests con `tmp_path` tal cual.

Si mockeas `@timer`:

```python
# MAL: anular @timer
monkeypatch.setattr("wx41.step_common.timer", lambda name: lambda fn: fn)

# El test luego intenta verificar:
assert "normalize" in ctx.timings  # FALLA - @timer nunca corrio, timings vacio
```

Si mockeas `atomic_output`:

```python
# MAL: anular atomic_output
monkeypatch.setattr("wx41.steps.normalize.atomic_output", contextlib.nullcontext)

# atomic_output nunca hace el rename tmp -> final
assert ctx.normalized.exists()  # FALLA - el archivo no llego al destino final
```

El test deja de verificar que el step realmente produce un archivo valido en disco.

---

## Que SI se nulifica con Nullable

Las tres funciones de infraestructura que llaman a FFmpeg real:

```python
# BIEN: Nullables para I/O externo (en conftest o en cada test)
monkeypatch.setattr("wx41.steps.normalize.extract_to_wav",
    lambda src, dst: True)                           # retorna True, no crea archivo

monkeypatch.setattr("wx41.steps.normalize.normalize_lufs",
    lambda src, dst, **kw: None)                     # no hace nada, tmp_norm sigue vacio

monkeypatch.setattr("wx41.steps.normalize.to_aac",
    lambda src, dst, **kw: (dst.touch(), True)[1])   # crea el archivo Y retorna True
```

`to_aac` necesita el `dst.touch()` porque `atomic_output` (que si corre real) va a hacer
`rename(tmp_out -> out)` -- ese `tmp_out` debe existir o falla con `FileNotFoundError`.

---

## El test completo y que verifica

```python
def test_normalize_step_walking_skeleton(tmp_path, monkeypatch):
    src = tmp_path / "video.mp3"
    src.write_bytes(b"fake")
    ctx = PipelineContext(src=src)

    monkeypatch.setattr("wx41.steps.normalize.extract_to_wav",
        lambda src, dst: True)
    monkeypatch.setattr("wx41.steps.normalize.normalize_lufs",
        lambda src, dst, **kw: None)
    monkeypatch.setattr("wx41.steps.normalize.to_aac",
        lambda src, dst, **kw: (dst.touch(), True)[1])

    result = normalize_step(ctx)

    assert result.normalized is not None,                      "normalize_step debe setear ctx.normalized"
    assert result.normalized.exists(),                         f"archivo no creado: {result.normalized}"
    assert result.normalized.name.endswith("_normalized.m4a"), f"sufijo: {result.normalized.name}"
    assert "normalize" in result.timings,                      f"timings actuales: {result.timings}"
    assert result.timings["normalize"] >= 0,                   f"timing invalido: {result.timings['normalize']}"

    assert not (tmp_path / "video._tmp_raw.wav").exists(),  "tmp_raw no limpiado"
    assert not (tmp_path / "video._tmp_norm.wav").exists(), "tmp_norm no limpiado"
```

`@timer` corrio real -> `timings["normalize"]` existe y es `>= 0`.
`atomic_output` corrio real -> `_normalized.m4a` existe en disco.
`temp_files` corrio real -> los `._tmp_*.wav` no existen.
FFmpeg nunca se invoco -> test corre en 2ms sin dependencias externas.

---

## lambda vs MagicMock: la diferencia practica

```python
# Nullable (lambda) - fuerza State-Based
monkeypatch.setattr("wx41.steps.normalize.extract_to_wav",
    lambda src, dst: True)
# El test verifica: assert result.normalized.exists()

# Mock (MagicMock) - tienta Interaction-Based
m = MagicMock(return_value=True)
monkeypatch.setattr("wx41.steps.normalize.extract_to_wav", m)
# Tentacion del test: m.assert_called_once_with(ctx.src, tmp_raw)  <- prohibido en wx41
```

Lambda fuerza a verificar **que quedo en disco y en `ctx`** (lo que importa al usuario).
MagicMock tienta a verificar **que se llamo con ciertos argumentos** (detalle de implementacion
que rompe tests con cualquier refactor interno).

---

## Resumen de la decision

| Que | Por que | Como |
|-----|---------|------|
| `step_common` (@timer, atomic_output, temp_files) | Solo usa Path + time, funciona en tmp_path | No tocar, corre real |
| `extract_to_wav`, `normalize_lufs`, `to_aac` | Necesitan FFmpeg real | Nullable via monkeypatch lambda |
| Verificaciones | Resultados en disco y ctx, no interacciones | State-Based, nunca assert_called_with |
