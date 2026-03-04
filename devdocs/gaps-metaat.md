# BRECHA 10: Meta-AT con metadata de steps y fixture centralizado

## Problema

El Meta-AT actual tiene conocimiento interno de los steps:

1. **Hardcoded needs_real_audio**: En `test_acceptance.py:672`:
   ```python
   needs_real_audio = step_name in {"normalize", "srt", "transcribe", "enhance"}
   ```
   Este conocimiento deberia estar en `StepInfo`, no en el test.

2. **Fixture path hardcodeado**: En `test_acceptance.py:674-676`:
   ```python
   fixture_path = Path(r"C:\workspace\@recordings\...m4a")
   ```
   Debe estar en `conftest.py` como fixture.

3. **StepInfo incompleta**: No tiene metadata sobre las necesidades del step.

---

## Plan de slices (ATDD/TDD)

### Slice 1: Extender StepInfo con needs_audio_fixture

**Objetivo**: Agregar campo `needs_audio_fixture` a `StepInfo` y registrar en cada step.

#### 1.1 AT en RED
Escribir test que verifique que `StepInfo` tiene el campo `needs_audio_fixture`.

```python
# test_acceptance.py (agregar en TestMetaATUnified)
def test_step_info_has_audio_fixture_metadata():
    from wx41.steps import get_all_steps
    
    steps = get_all_steps()
    
    assert "normalize" in steps
    assert steps["normalize"].needs_audio_fixture is True
    
    assert "compress" in steps
    assert steps["compress"].needs_audio_fixture is False
```

#### 1.2 Mejorar mensaje de fallo
El test fallara con: `AttributeError: 'StepInfo' object has no attribute 'needs_audio_fixture'`

#### 1.3 Unit test en RED
Agregar test unitario para `StepInfo` en `test_steps_registry.py`.

#### 1.4 Produccion GREEN
1. Editar `wx41/steps/__init__.py` - agregar `needs_audio_fixture: bool = False` a `StepInfo`
2. Editar cada step para passing `needs_audio_fixture=True`:
   - `wx41/steps/normalize.py`
   - `wx41/steps/srt.py`
   - `wx41/steps/transcribe.py`
   - `wx41/steps/enhance.py`

#### 1.5 Commit
`git commit -m "Add needs_audio_fixture to StepInfo"`

---

### Slice 2: Mover fixture a conftest.py

**Objetivo**: Centralizar el fixture de audio en `conftest.py`.

#### 2.1 AT en RED
Escribir test que use el fixture desde conftest.

```python
# test_acceptance.py
def test_uses_audio_fixture_from_conftest(audio_fixture_path):
    assert audio_fixture_path.exists()
    # El test parametrizado usara este fixture
```

#### 2.2 Produccion GREEN
1. Crear/editar `wx41/tests/conftest.py`:
   ```python
   @pytest.fixture
   def audio_fixture_path():
       path = Path(r"C:\workspace\@recordings\20260304 Bci Seguros Data\new\fidelizacion\20260304_130208.m4a")
       if not path.exists():
           pytest.skip(f"Fixture not found: {path}")
       return path
   ```

2. Refactorizar `TestMetaATUnified` para usar `audio_fixture_path`

#### 2.3 Commit
`git commit -m "Move audio fixture to conftest.py"`

---

### Slice 3: Refactorizar MetaAT para usar metadata del step

**Objetivo**: Eliminar hardcoded `needs_real_audio` y usar `step_info.needs_audio_fixture`.

#### 3.1 AT en RED
El test ya fue escrito en Slice 1 - fallara porque usa atributo que no existe.

#### 3.2 Produccion GREEN
Editar `test_acceptance.py`:
```python
# Antes (linea 672):
needs_real_audio = step_name in {"normalize", "srt", "transcribe", "enhance"}

# Despues:
step_info = get_step_info(step_name)
needs_real_audio = step_info.needs_audio_fixture
```

#### 3.3 Commit
`git commit -m "Use StepInfo.needs_audio_fixture in MetaAT"`

---

### Slice 4: Agregar input_media_type a StepInfo

**Objetivo**: Distinguir steps que requieren audio vs video.

#### 4.1 AT en RED
```python
def test_step_info_has_media_type():
    from wx41.steps import get_all_steps
    
    # audio steps
    assert get_all_steps()["normalize"].input_media_type == "audio"
    assert get_all_steps()["srt"].input_media_type == "audio"
    
    # video steps
    assert get_all_steps()["compress"].input_media_type == "video"
    assert get_all_steps()["black_video"].input_media_type == "video"
```

#### 4.2 Produccion GREEN
1. Agregar `input_media_type: str = "audio"` a `StepInfo`
2. Registrar en cada step:
   - `compress.py`: `input_media_type="video"`
   - `black_video.py`: `input_media_type="video"`
   - Los demas usan default "audio"

#### 4.3 Commit
`git commit -m "Add input_media_type to StepInfo"`

---

### Slice 5: Agregar variantes de config a StepInfo

**Objetivo**: Las variantes de configuracion deben definirse en el step, no hardcodeadas en MetaAT.

#### 5.1 AT en RED
```python
def test_step_info_provides_config_variants():
    from wx41.steps import get_step_info
    
    srt_info = get_step_info("srt")
    variants = srt_info.config_variants
    
    assert len(variants) >= 2
    assert any(v.mode == "words" for v in variants)
    assert any(v.mode == "sentences" for v in variants)
```

#### 5.2 Produccion GREEN
1. Agregar `config_variants: tuple = ()` a `StepInfo`
2. En cada step, definir variantes relevantes:
   - `srt.py`: variants con diferentes `mode`, `max_chars`, `generate_both`
   - `transcribe.py`: variants con diferentes `backend`

#### 5.3 Commit
`git commit -m "Add config_variants to StepInfo"`

---

### Slice 6: Regenerar MetaAT desde registry dinamicamente

**Objetivo**: El MetaAT se genera completamente desde `get_all_steps()` + `config_variants`.

#### 6.1 AT en RED
```python
def test_meta_at_covers_all_steps_and_variants():
    from wx41.steps import get_all_steps
    
    all_steps = get_all_steps()
    
    for step_name, step_info in all_steps.items():
        # Por lo menos la config default debe estar
        assert step_name in registry_test_names
```

#### 6.2 Produccion GREEN
Refactorizar `_get_all_step_variants()` para que use `config_variants` de cada step.

```python
def _get_all_step_variants():
    from wx41.steps import get_all_steps
    
    variants = []
    for step_name, step_info in get_all_steps().items():
        # Default variant
        variants.append((step_name, "default", None, False))
        variants.append((step_name, "default", None, True))
        
        # Config variants from step
        for variant_cfg in step_info.config_variants:
            variants.append((step_name, variant_cfg.name, variant_cfg.config, False))
    
    return variants
```

#### 6.3 Commit
`git commit -m "Regenerate MetaAT from registry dynamically"`

---

## Estado final

Despues de todos los slices:

- `StepInfo` tiene: `name`, `step_fn`, `config_class`, `output_fn`, `optional`, `description`, `needs_audio_fixture`, `input_media_type`, `config_variants`
- MetaAT usa solo metadata del registry
- Fixture centralizado en `conftest.py`
- No hay conocimiento hardcodeado de steps en el test

---

## Relacion con BRECHA 9

BRECHA 9 era: "unificar tests con mocks y fixture real"

BRECHA 10 es: "eliminar conocimiento hardcodeado del MetaAT hacia los steps"

Son complementarias - BRECHA 10 mejora la arquitectura interna del MetaAT.
