# Plan: Limpieza de argumentos CLI y arquitectura del pipeline

## Objetivo

1. Sincronizar tests con el estado actual de los flags CLI (ya renombrados)
2. Separar normalize_step de enhance_step en el pipeline
3. Agregar cache para archivos normalizados

---

## Estado actual (baseline)

**AVISO IMPORTANTE**: Los flags CLI YA fueron renombrados en cli.py de una sesion anterior. El trabajo consiste en sincronizar los tests con el codigo actual.

Flags actuales en cli.py:
- `--no-enhance` (antes `--skip-enhance`)
- `--video-output` (antes `--videooutput`)
- `--whisper-hf-token` (antes `--hf-token`)
- `--whisper-device` (antes `--device`)
- `--whisper-model`
- `--transcribe-backend` (antes `--backend`)
- `--srt-mode`

Fields actuales en context.py:
- `PipelineConfig.compress_ratio` (antes `compress`)
- `PipelineContext.enhanced`

**Ejecutar suite antes de empezar:**
```bash
python -m pytest wx4/tests/ -v --tb=no
```

Estado actual: **20 tests fallan, 249 pasan**

---

## Slice 0 — Baseline GREEN

### Tests que fallan por flags/campos desactualizados

| Test file | Test roto | Causa |
|---|---|---|
| test_cli.py | test_skip_enhance_flag_forwarded | usa `--skip-enhance`, ahora es `--no-enhance` |
| test_cli.py | test_videooutput_flag_forwarded | usa `--videooutput`, ahora es `--video-output` |
| test_cli.py | test_compress_flag_forwarded_to_build_steps | usa `compress=True`, ahora es `compress_ratio=0.4` |
| test_cli.py | test_compress_ratio_forwarded_to_context | flag no existe, eliminar test |
| test_cli.py | test_compress_encoder_forwarded_to_context | flag no existe, eliminar test |
| test_cli.py | test_skip_enhance_includes_callback_too | usa `--skip-enhance`, ahora es `--no-enhance` |
| test_cli.py | test_default_backend_is_assemblyai | busca `--backend`, ahora es `--transcribe-backend` |
| test_cli.py | test_backend_flag_forwarded_to_context | usa `--backend`, ahora es `--transcribe-backend` |
| test_cli.py | test_hf_token_flag_forwarded_to_context | usa `--hf-token`, ahora es `--whisper-hf-token` |
| test_cli.py | test_device_flag_forwarded_to_context | usa `--device`, ahora es `--whisper-device` |
| test_cli.py | test_whisper_model_flag_forwarded_to_context | usa `--whisper-model`, ahora es `--whisper-model` (verificar) |
| test_context.py | test_minimal_construction_no_args | busca `cfg.compress`, ahora es `cfg.compress_ratio` |
| test_context.py | test_can_construct_with_flags | usa `compress=True`, ahora es `compress_ratio=0.4` |
| test_context.py | test_defaults_are_correct | busca `ctx.compress_encoder`, no existe |
| test_pipeline.py | TestBuildSteps::test_compress_* | usa `compress=True`, ahora es `compress_ratio` |
| test_steps.py | test_calls_detect_encoder_with_compress_encoder | busca `compress_encoder`, ahora usa `force=None` |

### RED -> GREEN

**test_cli.py:**
- `test_skip_enhance_flag_forwarded`: cambiar `--skip-enhance` -> `--no-enhance`
- `test_videooutput_flag_forwarded`: cambiar `--videooutput` -> `--video-output`, assert `config.videooutput is True`
- `test_compress_flag_forwarded`: cambiar a `PipelineConfig(compress_ratio=0.4)`
- `test_compress_ratio_forwarded_to_context`: eliminar (flag no existe)
- `test_compress_encoder_forwarded_to_context`: eliminar (flag no existe)
- `test_skip_enhance_includes_callback_too`: cambiar `--skip-enhance` -> `--no-enhance`
- Tests en TestCliWhisperFlags: actualizar flags a `--transcribe-backend`, `--whisper-hf-token`, `--whisper-device`, `--whisper-model`

**test_context.py:**
- `test_minimal_construction_no_args`: cambiar `cfg.compress` -> `cfg.compress_ratio is None`
- `test_can_construct_with_flags`: cambiar `compress=True` -> `compress_ratio=0.4`
- `test_defaults_are_correct`: eliminar assert de `ctx.compress_encoder`

**test_pipeline.py (TestBuildSteps):**
- `test_compress_flag_appends_compress_step`: `PipelineConfig(compress=True)` -> `PipelineConfig(compress_ratio=0.4)`
- `test_no_compress_step_when_compress_false`: -> `compress_ratio=None`
- `test_compress_step_is_last_when_no_videooutput`: -> `compress_ratio=0.4`
- `test_compress_step_is_last_even_with_videooutput`: -> `compress_ratio=0.4`
- `test_compress_step_has_output_fn`: -> `compress_ratio=0.4`

**test_steps.py:**
- `test_calls_detect_encoder_with_compress_encoder`: cambiar a `_ctx(tmp_path, compress_ratio=0.40)` y verificar que `detect_best_encoder` se llama con `force=None`

```bash
python -m pytest wx4/tests/ -v   # -> GREEN
git commit -m "fix(tests): sync test suite with post-compress refactor baseline"
git push
```

---

## PARTE B: Separar normalize_step de enhance_step

### Diseno

```
normalize_step:  extract_to_wav + normalize_lufs + to_aac -> ctx.normalized (_normalized.m4a)
enhance_step:    apply_clearvoice(ctx.normalized | ctx.src) + to_aac -> ctx.enhanced (_enhanced.m4a)
transcribe_step: usa ctx.enhanced | ctx.normalized | ctx.src (en ese orden)
```

**Cache:**
- Si skip_enhance=False: guarda _enhanced.m4a (como ahora)
- Si skip_enhance=True Y skip_normalize=False: guarda _normalized.m4a
- Si skip_enhance=True Y skip_normalize=True: no guarda cache

Pipeline segun flags:

| --no-normalize | --no-enhance | Steps activos | Audio a transcribir |
|---|---|---|---|
| False | False | normalize -> enhance | _enhanced.m4a |
| False | True | normalize | _normalized.m4a |
| True | False | enhance | _enhanced.m4a |
| True | True | (ninguno) | src original |

---

### Slice B1 — PipelineContext: agregar ctx.normalized

**RED:** test_context.py — agregar a `test_defaults_are_correct`:
```python
assert ctx.normalized is None
```

```bash
python -m pytest wx4/tests/test_context.py::TestPipelineContext::test_defaults_are_correct  # RED
```

**GREEN:** en context.py agregar campo a PipelineContext:
```python
normalized: Optional[Path] = None
```

```bash
python -m pytest wx4/tests/ -v   # GREEN
git commit -m "feat(context): add ctx.normalized field for normalize_step output"
git push
```

---

### Slice B2 — PipelineConfig: agregar skip_normalize

**RED:** test_context.py — agregar a `TestPipelineConfig`:
```python
def test_skip_normalize_defaults_to_false(self):
    from wx4.context import PipelineConfig
    assert PipelineConfig().skip_normalize is False

def test_can_set_skip_normalize(self):
    from wx4.context import PipelineConfig
    cfg = PipelineConfig(skip_normalize=True)
    assert cfg.skip_normalize is True
```

```bash
python -m pytest wx4/tests/test_context.py::TestPipelineConfig  # RED
```

**GREEN:** en context.py agregar a PipelineConfig:
```python
skip_normalize: bool = False
```

```bash
python -m pytest wx4/tests/ -v   # GREEN
git commit -m "feat(context): add PipelineConfig.skip_normalize flag"
git push
```

---

### Slice B3 — normalize_step: nueva funcion en steps.py

**RED:** test_steps.py — nueva clase `TestNormalizeStep`:
```python
class TestNormalizeStep:
    def test_calls_extract_normalize_encode(self, tmp_path):
        ctx = _ctx(tmp_path, cache_hit=False, output_m4a=True)
        def fake_to_aac(src, dst, **kw):
            dst.write_bytes(b"aac")
            return True
        with patch("wx4.steps.extract_to_wav", return_value=True) as m_ext, \
             patch("wx4.steps.normalize_lufs") as m_norm, \
             patch("wx4.steps.to_aac", side_effect=fake_to_aac) as m_enc:
            from wx4.steps import normalize_step
            result = normalize_step(ctx)
        m_ext.assert_called_once()
        m_norm.assert_called_once()
        m_enc.assert_called_once()
        assert result.normalized is not None
        assert result.normalized.name.endswith("_normalized.m4a")

    def test_skips_on_cache_hit(self, tmp_path):
        norm = tmp_path / "audio_normalized.m4a"
        ctx = _ctx(tmp_path, cache_hit=True, normalized=norm)
        with patch("wx4.steps.extract_to_wav") as m_ext:
            from wx4.steps import normalize_step
            result = normalize_step(ctx)
        m_ext.assert_not_called()
        assert result.normalized == norm

    def test_does_not_call_apply_clearvoice(self, tmp_path):
        ctx = _ctx(tmp_path, cache_hit=False, output_m4a=True)
        def fake_to_aac(src, dst, **kw):
            dst.write_bytes(b"aac")
            return True
        with patch("wx4.steps.extract_to_wav", return_value=True), \
             patch("wx4.steps.normalize_lufs"), \
             patch("wx4.steps.to_aac", side_effect=fake_to_aac), \
             patch("wx4.steps.apply_clearvoice") as m_cv:
            from wx4.steps import normalize_step
            normalize_step(ctx)
        m_cv.assert_not_called()

    def test_timing_recorded(self, tmp_path):
        ctx = _ctx(tmp_path, cache_hit=False, output_m4a=True)
        def fake_to_aac(src, dst, **kw):
            dst.write_bytes(b"aac")
            return True
        with patch("wx4.steps.extract_to_wav", return_value=True), \
             patch("wx4.steps.normalize_lufs"), \
             patch("wx4.steps.to_aac", side_effect=fake_to_aac):
            from wx4.steps import normalize_step
            result = normalize_step(ctx)
        assert "normalize" in result.timings
```

Actualizar `TestEnhanceStep::test_calls_extract_normalize_enhance_encode_on_miss` para verificar que enhance_step ya NO llama extract_to_wav ni normalize_lufs:
```python
def test_calls_only_clearvoice_and_encode_on_miss(self, tmp_path):
    ctx = _ctx(tmp_path, cache_hit=False, output_m4a=True, cv=MagicMock())
    def fake_to_aac(src, dst, **kw):
        dst.write_bytes(b"aac")
        return True
    with patch("wx4.steps.apply_clearvoice") as m_cv, \
         patch("wx4.steps.to_aac", side_effect=fake_to_aac), \
         patch("wx4.steps.extract_to_wav") as m_ext, \
         patch("wx4.steps.normalize_lufs") as m_norm:
        from wx4.steps import enhance_step
        result = enhance_step(ctx)
    m_ext.assert_not_called()
    m_norm.assert_not_called()
    m_cv.assert_called_once()
    assert result.enhanced is not None
```

```bash
python -m pytest wx4/tests/test_steps.py::TestNormalizeStep  # RED
python -m pytest wx4/tests/test_steps.py::TestEnhanceStep    # RED
```

**GREEN:** en steps.py:
- Crear `normalize_step`: extract_to_wav + normalize_lufs + to_aac -> ctx.normalized
- Modificar `enhance_step`: recibe ctx.normalized (o ctx.src si None) -> clearvoice + to_aac -> ctx.enhanced

**Verificar atomicidad:** los tests de `TestEnhanceStepAtomicity` deben seguir pasando.

```bash
python -m pytest wx4/tests/ -v   # GREEN
git commit -m "feat(steps): split normalize_step from enhance_step"
git push
```

---

### Slice B4 — pipeline.py: build_steps usa skip_normalize + cache

**RED:** test_pipeline.py — agregar a `TestBuildSteps`:
```python
def test_default_has_normalize_step(self):
    from wx4.pipeline import build_steps
    from wx4.steps import normalize_step
    fns = self._fns(build_steps())
    assert normalize_step in fns

def test_skip_normalize_removes_normalize_step(self):
    from wx4.pipeline import build_steps
    from wx4.steps import normalize_step
    from wx4.context import PipelineConfig
    fns = self._fns(build_steps(PipelineConfig(skip_normalize=True)))
    assert normalize_step not in fns

def test_skip_normalize_keeps_enhance_step(self):
    from wx4.pipeline import build_steps
    from wx4.steps import enhance_step
    from wx4.context import PipelineConfig
    fns = self._fns(build_steps(PipelineConfig(skip_normalize=True)))
    assert enhance_step in fns

def test_skip_normalize_and_skip_enhance_removes_both(self):
    from wx4.pipeline import build_steps
    from wx4.steps import normalize_step, enhance_step
    from wx4.context import PipelineConfig
    fns = self._fns(build_steps(PipelineConfig(skip_normalize=True, skip_enhance=True)))
    assert normalize_step not in fns
    assert enhance_step not in fns

def test_normalize_comes_before_enhance(self):
    from wx4.pipeline import build_steps, NamedStep
    from wx4.steps import normalize_step, enhance_step
    steps = build_steps()
    fns = self._fns(steps)
    assert fns.index(normalize_step) < fns.index(enhance_step)

def test_normalize_step_has_output_fn(self):
    from wx4.pipeline import NamedStep, build_steps
    from wx4.steps import normalize_step
    steps = build_steps()
    norm = next(s for s in steps if isinstance(s, NamedStep) and s.fn is normalize_step)
    assert norm.output_fn is not None
```

```bash
python -m pytest wx4/tests/test_pipeline.py::TestBuildSteps  # RED
```

**GREEN:** en pipeline.py:
- Agregar `_NORMALIZE_OUT = lambda ctx: ctx.src.parent / f"{ctx.src.stem}_normalized.m4a"`
- En `build_steps()`:
  ```python
  if not config.skip_enhance:
      steps.append(NamedStep("cache_check", cache_check_step))
      if not config.skip_normalize:
          steps.append(NamedStep("normalize", normalize_step, _NORMALIZE_OUT))
      steps.append(NamedStep("enhance", enhance_step, _ENHANCE_OUT))
      steps.append(NamedStep("cache_save", cache_save_step))
  ```
- Actualizar cache_check_step para buscar _normalized.m4a si skip_enhance=True
- Actualizar cache_save_step para guardar _normalized.m4a si skip_enhance=True Y skip_normalize=False
- Actualizar docstring de build_steps()

```bash
python -m pytest wx4/tests/ -v   # GREEN
git commit -m "feat(pipeline): build_steps respects skip_normalize config flag"
git push
```

---

### Slice B5 — CLI: agregar --no-normalize

**RED:** test_cli.py — agregar:
```python
def test_no_normalize_flag_forwarded(self, tmp_path):
    from typer.testing import CliRunner
    from wx4.cli import app
    from wx4.context import PipelineConfig
    f = tmp_path / "audio.mp3"
    f.write_bytes(b"audio")
    mock_ctx = _make_ctx(tmp_path)
    with patch("wx4.cli.Pipeline") as M, patch("wx4.cli.build_steps") as mock_build:
        M.return_value.run.return_value = mock_ctx
        mock_build.return_value = []
        CliRunner().invoke(app, [str(f), "--no-normalize"])
    config = mock_build.call_args.args[0]
    assert isinstance(config, PipelineConfig)
    assert config.skip_normalize is True

def test_no_normalize_without_no_enhance_keeps_enhance(self, tmp_path):
    from typer.testing import CliRunner
    from wx4.cli import app
    from wx4.context import PipelineConfig
    f = tmp_path / "audio.mp3"
    f.write_bytes(b"audio")
    mock_ctx = _make_ctx(tmp_path)
    with patch("wx4.cli.Pipeline") as M, patch("wx4.cli.build_steps") as mock_build:
        M.return_value.run.return_value = mock_ctx
        mock_build.return_value = []
        CliRunner().invoke(app, [str(f), "--no-normalize"])
    config = mock_build.call_args.args[0]
    assert config.skip_enhance is False
```

```bash
python -m pytest wx4/tests/test_cli.py::TestCli::test_no_normalize_flag_forwarded  # RED
```

**GREEN:** en cli.py agregar:
```python
skip_normalize: bool = typer.Option(False, "--no-normalize", help="Skip LUFS audio normalization"),
```
y pasar `skip_normalize=skip_normalize` a PipelineConfig.

```bash
python -m pytest wx4/tests/ -v   # GREEN
git commit -m "feat(cli): add --no-normalize flag for independent normalize control"
git push
```

---

### Slice B6 — Acceptance: normalize y enhance independientes

**RED:** test_acceptance.py — agregar:
```python
def test_no_normalize_skips_normalize_step(self, tmp_path):
    """--no-normalize: normalize_step no corre, enhance_step (clearvoice) si."""
    src = tmp_path / "audio.mp3"
    src.write_bytes(b"audio")
    words = [{"text": "hi.", "start": 0, "end": 500, "speaker": "A"}]
    transcribe_mock = _make_transcribe_mock(tmp_path, "audio_enhanced", words)

    with patch("wx4.steps.transcribe_assemblyai", side_effect=transcribe_mock), \
         patch("wx4.steps.apply_clearvoice") as m_cv, \
         patch("wx4.steps.normalize_lufs") as m_norm, \
         patch("wx4.steps.extract_to_wav") as m_ext, \
         patch("wx4.steps.to_aac", side_effect=lambda s,d,**kw: (d.write_bytes(b"aac") or True)):
        from wx4.context import PipelineConfig, PipelineContext
        from wx4.pipeline import Pipeline, build_steps
        ctx = PipelineContext(src=src, cv=MagicMock())
        steps = build_steps(PipelineConfig(skip_normalize=True))
        result = Pipeline(steps).run(ctx)

    m_norm.assert_not_called()
    m_ext.assert_not_called()
    m_cv.assert_called_once()
    assert result.srt is not None

def test_no_enhance_skips_clearvoice(self, tmp_path):
    """--no-enhance: clearvoice no corre, normalize si."""
    src = tmp_path / "audio.mp3"
    src.write_bytes(b"audio")
    words = [{"text": "hi.", "start": 0, "end": 500, "speaker": "A"}]
    transcribe_mock = _make_transcribe_mock(tmp_path, "audio_normalized", words)

    with patch("wx4.steps.transcribe_assemblyai", side_effect=transcribe_mock), \
         patch("wx4.steps.apply_clearvoice") as m_cv, \
         patch("wx4.steps.extract_to_wav", return_value=True), \
         patch("wx4.steps.normalize_lufs"), \
         patch("wx4.steps.to_aac", side_effect=lambda s,d,**kw: (d.write_bytes(b"aac") or True)):
        from wx4.context import PipelineConfig, PipelineContext
        from wx4.pipeline import Pipeline, build_steps
        ctx = PipelineContext(src=src)
        steps = build_steps(PipelineConfig(skip_enhance=True))
        result = Pipeline(steps).run(ctx)

    m_cv.assert_not_called()
    assert result.srt is not None
```

```bash
python -m pytest wx4/tests/test_acceptance.py  # RED
```

**GREEN:** Si los slices B1-B5 estan completos, estos tests pasan sin codigo nuevo.

```bash
python -m pytest wx4/tests/ -v   # GREEN (suite completa)
git commit -m "test(acceptance): add AT for independent normalize/enhance control"
git push
```

---

## Resumen de slices

| Slice | Cambio | Archivos |
|-------|--------|----------|
| 0 | Baseline GREEN (sincronizar tests con flags actuales) | test_*.py |
| B1 | ctx.normalized field | context.py + test_context.py |
| B2 | PipelineConfig.skip_normalize | context.py + test_context.py |
| B3 | normalize_step separado de enhance_step | steps.py + test_steps.py |
| B4 | build_steps usa skip_normalize + cache | pipeline.py + test_pipeline.py |
| B5 | --no-normalize en CLI | cli.py + test_cli.py |
| B6 | AT para normalize/enhance independientes | test_acceptance.py |

## Estado final del --help

```
[FILES]...

--language / -l       TEXT     Idioma: es, en, ... (default: auto)
--speakers / -s       INT      Numero de speakers (default: auto)
--srt-mode            TEXT     speaker-only | sentences (default: speaker-only)
--speakers-map        TEXT     A=Marcel,B=Agustin

--no-normalize                 Saltar normalizacion LUFS
--no-enhance                   Saltar ClearVoice (MossFormer2_SE_48K)
--force                        Re-procesar ignorando cache
--video-output                 Generar MP4 de salida
--compress            FLOAT    Comprimir video al ratio dado (ej: 0.4)

--transcribe-backend  TEXT     assemblyai | whisper (default: assemblyai)
--assemblyai-api-key  TEXT     API key AssemblyAI (o env ASSEMBLY_AI_KEY)
--whisper-model       TEXT     Modelo Whisper (default: openai/whisper-large-v3)
--whisper-device      TEXT     auto | cpu | cuda | mps (default: auto)
--whisper-hf-token    TEXT     Token HuggingFace para PyAnnote
```
