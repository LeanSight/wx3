# Plan: Integrar compress_video.py como paso opcional en wx4
## Metodologia: ATDD + TDD + One-Piece-Flow

Cada slice sigue RED -> GREEN -> REFACTOR antes de avanzar al siguiente.
Los tests existentes se modifican/extienden para ir a RED primero;
los tests nuevos se crean en RED antes de escribir produccion.

---

## Archivos de tests afectados

| Archivo | Tipo de cambio |
|---|---|
| `wx4/tests/test_context.py` | Extender test existente -> RED |
| `wx4/tests/test_pipeline.py` | Agregar tests nuevos -> RED |
| `wx4/tests/test_steps.py` | Agregar clase nueva -> RED |
| `wx4/tests/test_cli.py` | Agregar tests nuevos -> RED |
| `wx4/tests/test_acceptance.py` | Agregar tests nuevos -> RED |

## Archivos de produccion afectados

| Archivo | Cambios |
|---|---|
| `wx4/compress_video.py` | Fix ASCII (prerequisito, no TDD) |
| `wx4/context.py` | +4 campos |
| `wx4/steps.py` | +compress_step() |
| `wx4/pipeline.py` | +_COMPRESS_OUT, actualizar build_steps() |
| `wx4/cli.py` | +3 opciones CLI, tabla resumen |

---

## Slice 0 - Fix ASCII en compress_video.py (prerequisito, no TDD)

Sin este fix, cualquier `import wx4.compress_video` dentro de los tests
puede crashear en Windows. Va primero, sin tests porque es un fix de compliance.

Cambios en `detect_best_encoder()`:
```python
# ANTES (crashea cp1252):
log.info("Detectando aceleracion de hardware disponible...")  # acento
log.info("OK Disponible: %s", enc)                           # emoji
log.debug("No disponible: %s (%s)", label, ffmpeg_name)      # emoji
log.info("Sin aceleracion HW detectada -> CPU (libx264)")    # flecha unicode
log.info("Encoder forzado: CPU")                             # OK ya

# DESPUES (ASCII puro):
log.info("Detectando aceleracion de hardware disponible...")
log.info("OK Disponible: %s", enc)
log.debug("No disponible: %s (%s)", label, ffmpeg_name)
log.info("Sin aceleracion HW detectada -> CPU (libx264)")
log.info("Encoder forzado: CPU")
```

Cambios en `main()`:
- `"Resolucion: ..."` (sin acento)
- `"Normalizacion LUFS: ..."` (sin acento)
- `"Audio silencioso -> sin normalizacion"` (flecha + acento)
- `"LUFS: %s -> %s ..."` (flecha unicode)
- `"Comprimiendo con %s -> %s"` (flecha unicode)

`print_summary()` se conserva intacto (solo se llama desde `__main__`, nunca
desde el step del pipeline).

---

## Slice 1 - PipelineContext conoce compress

### 1a) RED: Extender test existente

**Archivo:** `wx4/tests/test_context.py`
**Test:** `TestPipelineContext::test_defaults_are_correct`

Agregar al final del metodo (despues del assert de `ctx.cv`):

```python
# compress fields
assert ctx.compress is False
assert ctx.compress_ratio == 0.40
assert ctx.compress_encoder is None
assert ctx.video_compressed is None
```

Ejecutar: `pytest wx4/tests/test_context.py::TestPipelineContext::test_defaults_are_correct`
-> **FALLA** con `AttributeError: 'PipelineContext' object has no attribute 'compress'`

### 1b) GREEN: Agregar campos a context.py

En `wx4/context.py`, despues de `videooutput: bool = False`:

```python
compress: bool = False
compress_ratio: float = 0.40
compress_encoder: Optional[str] = None
video_compressed: Optional[Path] = None
```

Ejecutar: misma prueba -> **VERDE**

### 1c) REFACTOR

Ninguno necesario.

---

## Slice 2 - build_steps() soporta flag compress

### 2a) RED: Tests nuevos en test_pipeline.py

**Archivo:** `wx4/tests/test_pipeline.py`
**Clase:** `TestBuildSteps` (agregar al final)

```python
def test_compress_flag_appends_compress_step(self):
    from wx4.pipeline import build_steps
    from wx4.steps import compress_step

    fns = self._fns(build_steps(compress=True))
    assert compress_step in fns

def test_no_compress_step_when_compress_false(self):
    from wx4.pipeline import build_steps
    from wx4.steps import compress_step

    fns = self._fns(build_steps(compress=False))
    assert compress_step not in fns

def test_compress_step_is_last_when_no_videooutput(self):
    from wx4.pipeline import NamedStep, build_steps
    from wx4.steps import compress_step

    steps = build_steps(compress=True, videooutput=False)
    last = steps[-1]
    fn = last.fn if isinstance(last, NamedStep) else last
    assert fn is compress_step

def test_compress_step_is_last_even_with_videooutput(self):
    """compress siempre va despues de video, comprimiendo el ORIGINAL."""
    from wx4.pipeline import NamedStep, build_steps
    from wx4.steps import compress_step

    steps = build_steps(compress=True, videooutput=True)
    last = steps[-1]
    fn = last.fn if isinstance(last, NamedStep) else last
    assert fn is compress_step

def test_compress_step_has_output_fn(self):
    from wx4.pipeline import NamedStep, build_steps
    from wx4.steps import compress_step

    steps = build_steps(compress=True)
    step = next(s for s in steps if isinstance(s, NamedStep) and s.fn is compress_step)
    assert step.output_fn is not None
```

Ejecutar: `pytest wx4/tests/test_pipeline.py::TestBuildSteps`
-> **FALLA** (compress_step no existe / build_steps no acepta compress=True)

### 2b) GREEN: Actualizar pipeline.py

Agregar lambda:
```python
_COMPRESS_OUT = lambda ctx: ctx.src.parent / f"{ctx.src.stem}_compressed.mp4"
```

Actualizar `build_steps()`:
```python
def build_steps(
    skip_enhance: bool = False,
    videooutput: bool = False,
    force: bool = False,
    compress: bool = False,
) -> List[NamedStep]:
    ...
    if compress:
        from wx4.steps import compress_step
        steps.append(NamedStep("compress", compress_step, _COMPRESS_OUT))

    return steps
```

Nota: `compress_step` aun no existe en steps.py. Los tests de pipeline se
satisfacen con el import lazy, pero fallaran en ejecucion real hasta el Slice 3.
Los tests de pipeline usan `self._fns()` que solo verifica identidad de funcion;
el import lazy hace que esto funcione siempre que `compress_step` exista en steps.py.

-> Por esto, Slice 2 y Slice 3 se ejecutan juntos: poner tests en RED, implementar
steps.py (Slice 3), luego confirmar que todo es GREEN.

---

## Slice 3 - compress_step comportamiento

### 3a) RED: Clase nueva en test_steps.py

**Archivo:** `wx4/tests/test_steps.py`
**Agregar al final:**

```python
# ---------------------------------------------------------------------------
# TestCompressStep
# ---------------------------------------------------------------------------


class TestCompressStep:
    """
    compress_step delega a funciones de compress_video, todas mockeadas.
    No se requiere ffmpeg real.
    """

    def _make_probe_info(self, has_audio=True, duration=60.0, width=1920, height=1080):
        info = MagicMock()
        info.has_audio = has_audio
        info.duration = duration
        info.width = width
        info.height = height
        return info

    def _make_lufs(self):
        return MagicMock()

    def _patch_all(self, info=None, lufs=None, encoder="libx264", bitrate=500_000):
        if info is None:
            info = self._make_probe_info()
        if lufs is None:
            lufs = self._make_lufs()
        return {
            "wx4.steps.probe_video": MagicMock(return_value=info),
            "wx4.steps.measure_audio_lufs": MagicMock(return_value=MagicMock()),
            "wx4.steps.LufsInfo": MagicMock(
                from_measured=MagicMock(return_value=lufs),
                noop=MagicMock(return_value=lufs),
            ),
            "wx4.steps.detect_best_encoder": MagicMock(return_value=encoder),
            "wx4.steps.calculate_video_bitrate": MagicMock(return_value=bitrate),
            "wx4.steps._compress_video": MagicMock(),
        }

    def test_calls_probe_video_with_src(self, tmp_path):
        ctx = _ctx(tmp_path, compress=True, compress_ratio=0.40)
        patches = self._patch_all()

        with patch.multiple("wx4.steps", **patches):
            from wx4.steps import compress_step
            compress_step(ctx)

        patches["wx4.steps.probe_video"].assert_called_once_with(ctx.src)

    def test_raises_clearly_when_probe_fails(self, tmp_path):
        ctx = _ctx(tmp_path, compress=True)
        with patch("wx4.steps.probe_video", side_effect=RuntimeError("not a video")):
            from wx4.steps import compress_step
            with pytest.raises(RuntimeError, match="compress_step"):
                compress_step(ctx)

    def test_measures_lufs_when_has_audio(self, tmp_path):
        ctx = _ctx(tmp_path, compress=True)
        info = self._make_probe_info(has_audio=True)
        patches = self._patch_all(info=info)

        with patch.multiple("wx4.steps", **patches):
            from wx4.steps import compress_step
            compress_step(ctx)

        patches["wx4.steps.measure_audio_lufs"].assert_called_once_with(ctx.src)

    def test_uses_lufs_noop_when_no_audio(self, tmp_path):
        ctx = _ctx(tmp_path, compress=True)
        info = self._make_probe_info(has_audio=False)
        patches = self._patch_all(info=info)

        with patch.multiple("wx4.steps", **patches):
            from wx4.steps import compress_step
            compress_step(ctx)

        patches["wx4.steps.measure_audio_lufs"].assert_not_called()
        patches["wx4.steps.LufsInfo"].noop.assert_called_once()

    def test_calls_detect_encoder_with_compress_encoder(self, tmp_path):
        ctx = _ctx(tmp_path, compress=True, compress_encoder="h264_nvenc")
        patches = self._patch_all()

        with patch.multiple("wx4.steps", **patches):
            from wx4.steps import compress_step
            compress_step(ctx)

        patches["wx4.steps.detect_best_encoder"].assert_called_once_with(force="h264_nvenc")

    def test_calls_calculate_bitrate_with_compress_ratio(self, tmp_path):
        ctx = _ctx(tmp_path, compress=True, compress_ratio=0.30)
        patches = self._patch_all()

        with patch.multiple("wx4.steps", **patches):
            from wx4.steps import compress_step
            compress_step(ctx)

        patches["wx4.steps.calculate_video_bitrate"].assert_called_once_with(
            patches["wx4.steps.probe_video"].return_value, 0.30
        )

    def test_calls_compress_video(self, tmp_path):
        ctx = _ctx(tmp_path, compress=True)
        patches = self._patch_all()

        with patch.multiple("wx4.steps", **patches):
            from wx4.steps import compress_step
            compress_step(ctx)

        patches["wx4.steps._compress_video"].assert_called_once()

    def test_sets_video_compressed_on_ctx(self, tmp_path):
        ctx = _ctx(tmp_path, compress=True)
        patches = self._patch_all()

        with patch.multiple("wx4.steps", **patches):
            from wx4.steps import compress_step
            result = compress_step(ctx)

        assert result.video_compressed is not None

    def test_output_path_is_src_stem_compressed_mp4(self, tmp_path):
        ctx = _ctx(tmp_path, compress=True)
        patches = self._patch_all()

        with patch.multiple("wx4.steps", **patches):
            from wx4.steps import compress_step
            result = compress_step(ctx)

        expected = ctx.src.parent / f"{ctx.src.stem}_compressed.mp4"
        assert result.video_compressed == expected

    def test_timing_recorded(self, tmp_path):
        ctx = _ctx(tmp_path, compress=True)
        patches = self._patch_all()

        with patch.multiple("wx4.steps", **patches):
            from wx4.steps import compress_step
            result = compress_step(ctx)

        assert "compress" in result.timings
```

Ejecutar: `pytest wx4/tests/test_steps.py::TestCompressStep`
-> **FALLA** (compress_step no existe en steps.py)

### 3b) GREEN: Agregar compress_step a steps.py

Agregar al final de `wx4/steps.py`:

```python
def compress_step(ctx: PipelineContext) -> PipelineContext:
    t0 = time.time()

    from wx4.compress_video import (
        LufsInfo,
        calculate_video_bitrate,
        compress_video as _compress_video,
        detect_best_encoder,
        measure_audio_lufs,
        probe_video,
    )

    src = ctx.src
    out = src.parent / f"{src.stem}_compressed.mp4"

    try:
        info = probe_video(src)
    except RuntimeError as exc:
        raise RuntimeError(
            f"compress_step: {src.name} is not a video file or probe failed: {exc}"
        ) from exc

    if info.has_audio:
        measured = measure_audio_lufs(src)
        lufs = LufsInfo.from_measured(measured)
    else:
        lufs = LufsInfo.noop()

    encoder = detect_best_encoder(force=ctx.compress_encoder)
    bitrate = calculate_video_bitrate(info, ctx.compress_ratio)
    _compress_video(info, lufs, encoder, bitrate, out)

    return dataclasses.replace(
        ctx, video_compressed=out, timings={**ctx.timings, "compress": time.time() - t0}
    )
```

Nota sobre mocking en tests: compress_video importa dentro de la funcion,
por lo que el mock debe parchear los nombres en el namespace de steps:
`wx4.steps.probe_video`, `wx4.steps._compress_video`, etc.
Para que esto funcione, los imports lazy deben hacerse al nivel del modulo
(importar al principio de la funcion y reasignarlos) o el test debe parchear
`wx4.compress_video.probe_video` antes del import. Ver nota de implementacion
en Apendice A.

Ejecutar: `pytest wx4/tests/test_steps.py wx4/tests/test_pipeline.py`
-> **VERDE**

### 3c) REFACTOR

Si el mocking de imports lazy es engorroso, refactorizar compress_step para
extraer los imports al modulo-level con guardas, o usar un helper `_get_compress_fns()`.
Solo si es necesario para que los tests sean mantenibles.

---

## Slice 4 - CLI expone --compress, --compress-ratio, --compress-encoder

### 4a) RED: Tests nuevos en test_cli.py

**Archivo:** `wx4/tests/test_cli.py`
**Agregar al final de `TestCli`:**

```python
def test_compress_flag_forwarded_to_build_steps(self, tmp_path):
    from typer.testing import CliRunner
    from wx4.cli import app

    f = tmp_path / "audio.mp3"
    f.write_bytes(b"audio")
    mock_ctx = _make_ctx(tmp_path)

    with patch("wx4.cli.Pipeline") as MockPipeline, patch(
        "wx4.cli.build_steps"
    ) as mock_build:
        MockPipeline.return_value.run.return_value = mock_ctx
        mock_build.return_value = []
        runner = CliRunner()
        runner.invoke(app, [str(f), "--compress"])

    call_kwargs = mock_build.call_args.kwargs
    assert call_kwargs.get("compress") is True

def test_compress_ratio_forwarded_to_context(self, tmp_path):
    from typer.testing import CliRunner
    from wx4.cli import app

    f = tmp_path / "audio.mp3"
    f.write_bytes(b"audio")
    mock_ctx = _make_ctx(tmp_path)
    captured = {}

    def fake_run(ctx):
        captured["compress_ratio"] = ctx.compress_ratio
        return mock_ctx

    with patch("wx4.cli.Pipeline") as MockPipeline, patch(
        "wx4.cli.build_steps", return_value=[]
    ):
        MockPipeline.return_value.run.side_effect = fake_run
        runner = CliRunner()
        runner.invoke(app, [str(f), "--compress", "--compress-ratio", "0.30"])

    assert captured.get("compress_ratio") == pytest.approx(0.30)

def test_compress_encoder_forwarded_to_context(self, tmp_path):
    from typer.testing import CliRunner
    from wx4.cli import app

    f = tmp_path / "audio.mp3"
    f.write_bytes(b"audio")
    mock_ctx = _make_ctx(tmp_path)
    captured = {}

    def fake_run(ctx):
        captured["compress_encoder"] = ctx.compress_encoder
        return mock_ctx

    with patch("wx4.cli.Pipeline") as MockPipeline, patch(
        "wx4.cli.build_steps", return_value=[]
    ):
        MockPipeline.return_value.run.side_effect = fake_run
        runner = CliRunner()
        runner.invoke(app, [str(f), "--compress", "--compress-encoder", "cpu"])

    assert captured.get("compress_encoder") == "cpu"

def test_summary_table_shows_compressed_when_video_compressed(self, tmp_path):
    from typer.testing import CliRunner
    from wx4.cli import app

    f = tmp_path / "audio.mp3"
    f.write_bytes(b"audio")
    compressed_path = tmp_path / "audio_compressed.mp4"
    mock_ctx = _make_ctx(tmp_path, video_compressed=compressed_path)

    with patch("wx4.cli.Pipeline") as MockPipeline, patch(
        "wx4.cli.build_steps", return_value=[]
    ):
        MockPipeline.return_value.run.return_value = mock_ctx
        runner = CliRunner()
        result = runner.invoke(app, [str(f)])

    assert "audio_compressed.mp4" in result.output

def test_summary_table_shows_dash_when_no_compressed(self, tmp_path):
    from typer.testing import CliRunner
    from wx4.cli import app

    f = tmp_path / "audio.mp3"
    f.write_bytes(b"audio")
    mock_ctx = _make_ctx(tmp_path, video_compressed=None)

    with patch("wx4.cli.Pipeline") as MockPipeline, patch(
        "wx4.cli.build_steps", return_value=[]
    ):
        MockPipeline.return_value.run.return_value = mock_ctx
        runner = CliRunner()
        result = runner.invoke(app, [str(f)])

    # La tabla debe renderizarse sin error; el valor "-" puede estar en la celda
    assert result.exit_code == 0
```

Ejecutar: `pytest wx4/tests/test_cli.py`
-> **FALLA** (--compress no existe como opcion)

### 4b) GREEN: Actualizar cli.py

a) Nuevas opciones Typer (despues de `api_key`):
```python
compress: bool = typer.Option(False, "--compress", help="Compress source video after transcription"),
compress_ratio: float = typer.Option(
    0.40, "--compress-ratio",
    help="Compression ratio (0.40 = 40%% of original size)"
),
compress_encoder: Optional[str] = typer.Option(
    None, "--compress-encoder",
    help="Force video encoder: cpu, h264_nvenc, h264_amf, h264_qsv"
),
```

b) Actualizar llamada a build_steps:
```python
steps = build_steps(
    skip_enhance=skip_enhance, videooutput=videooutput,
    force=force, compress=compress,
)
```

c) Actualizar creacion de PipelineContext:
```python
pipeline_ctx = PipelineContext(
    ...
    compress=compress,
    compress_ratio=compress_ratio,
    compress_encoder=compress_encoder,
)
```

d) Actualizar tabla resumen:
```python
table.add_column("Compressed")
...
compressed = result_ctx.video_compressed.name if result_ctx.video_compressed else "-"
table.add_row(result_ctx.src.name, srt_name, compressed)
```

Ejecutar: `pytest wx4/tests/test_cli.py`
-> **VERDE**

### 4c) REFACTOR

Ninguno necesario.

---

## Slice 5 - Acceptance: compress en el pipeline completo

### 5a) RED: Tests nuevos en test_acceptance.py

**Archivo:** `wx4/tests/test_acceptance.py`
**Agregar al final de `TestAcceptance`:**

```python
def test_compress_produces_video_compressed(self, tmp_path):
    """compress=True -> result.video_compressed es Path con sufijo _compressed.mp4."""
    src = tmp_path / "meeting.mp4"
    src.write_bytes(b"fake video")

    words = [{"text": "hi.", "start": 0, "end": 500, "speaker": "A"}]
    transcribe_mock = _make_transcribe_mock(tmp_path, "meeting", words)

    with (
        patch("wx4.steps.transcribe_assemblyai", side_effect=transcribe_mock),
        patch("wx4.steps.probe_video") as mock_probe,
        patch("wx4.steps.measure_audio_lufs", return_value=MagicMock()),
        patch("wx4.steps.LufsInfo") as mock_lufs_cls,
        patch("wx4.steps.detect_best_encoder", return_value="libx264"),
        patch("wx4.steps.calculate_video_bitrate", return_value=500_000),
        patch("wx4.steps._compress_video"),
    ):
        mock_probe.return_value = MagicMock(has_audio=True, duration=60.0)
        mock_lufs_cls.from_measured.return_value = MagicMock()

        from wx4.context import PipelineContext
        from wx4.pipeline import Pipeline, build_steps

        ctx = PipelineContext(src=src, skip_enhance=True, compress=True)
        steps = build_steps(skip_enhance=True, compress=True)
        pipeline = Pipeline(steps)
        result = pipeline.run(ctx)

    assert result.video_compressed is not None
    assert result.video_compressed.name == "meeting_compressed.mp4"

def test_pipeline_without_compress_leaves_video_compressed_none(self, tmp_path):
    """compress=False (default) -> result.video_compressed es None."""
    src = tmp_path / "audio.mp3"
    src.write_bytes(b"audio")

    words = [{"text": "hi.", "start": 0, "end": 500, "speaker": "A"}]
    transcribe_mock = _make_transcribe_mock(tmp_path, "audio", words)

    with patch("wx4.steps.transcribe_assemblyai", side_effect=transcribe_mock):
        from wx4.context import PipelineContext
        from wx4.pipeline import Pipeline, build_steps

        ctx = PipelineContext(src=src, skip_enhance=True, compress=False)
        steps = build_steps(skip_enhance=True, compress=False)
        pipeline = Pipeline(steps)
        result = pipeline.run(ctx)

    assert result.video_compressed is None
```

Ejecutar: `pytest wx4/tests/test_acceptance.py`
-> **FALLA** (compress_step / compress=True en build_steps no implementado aun
si los slices anteriores no estan completos; con los slices anteriores completos -> VERDE)

### 5b) GREEN

No hay produccion nueva aqui. Si los Slices 0-4 estan completos, estos
tests pasan directamente. Si algo falla, diagnosticar en que slice hay un gap.

### 5c) REFACTOR

Ninguno necesario.

---

## Orden de ejecucion (one-piece-flow)

```
[Slice 0] Fix ASCII en compress_video.py
    -> pytest wx4/tests/ (baseline, todo verde)

[Slice 1] RED: extender test_context -> GREEN: context.py
    -> pytest wx4/tests/test_context.py

[Slice 2+3] RED: test_pipeline + test_steps -> GREEN: pipeline.py + steps.py
    (se juntan porque el test de pipeline necesita que compress_step exista)
    -> pytest wx4/tests/test_pipeline.py wx4/tests/test_steps.py

[Slice 4] RED: test_cli -> GREEN: cli.py
    -> pytest wx4/tests/test_cli.py

[Slice 5] RED: test_acceptance -> GREEN: (deberia pasar sin codigo nuevo)
    -> pytest wx4/tests/test_acceptance.py

[Final] Suite completa
    -> pytest wx4/tests/
```

---

## Apendice A - Mocking de imports lazy en compress_step

`compress_step` importa desde `wx4.compress_video` dentro de la funcion.
Para que `patch("wx4.steps.probe_video")` funcione, los nombres deben estar
en el namespace de `wx4.steps` al momento del patch.

Dos opciones:

**Opcion 1 (recomendada): importar al inicio de la funcion y reasignar locales**
```python
def compress_step(ctx):
    from wx4.compress_video import (
        LufsInfo,
        calculate_video_bitrate,
        compress_video as _compress_video,
        detect_best_encoder,
        measure_audio_lufs,
        probe_video,
    )
    # Desde aqui, los nombres son locales -> patch("wx4.steps.probe_video") NO funciona.
    # El test debe parchear wx4.compress_video.probe_video directamente.
```

**Opcion 2: importar al nivel de modulo con try/except (mejor testabilidad)**
```python
# Al inicio de steps.py, fuera de cualquier funcion:
try:
    from wx4.compress_video import (
        LufsInfo, calculate_video_bitrate,
        compress_video as _compress_video,
        detect_best_encoder, measure_audio_lufs, probe_video,
    )
except ImportError:
    pass  # solo disponible cuando compress_video esta instalado
```

Con la Opcion 2, los mocks deben ser `patch("wx4.steps.probe_video")` etc.
Con la Opcion 1, los mocks deben ser `patch("wx4.compress_video.probe_video")` etc.

**Elegir una opcion y ajustar los tests en consecuencia.**
La Opcion 2 es mas testeable pero agrega imports al modulo.
La Opcion 1 mantiene los imports lazy (evita cargar ffmpeg en cada import de steps)
pero requiere parchear en el namespace de compress_video.

---

## Verificacion final (comandos manuales)

```bash
# Test basico
python -m wx4 meeting.mp4 --skip-enhance --compress

# Test con ratio
python -m wx4 meeting.mp4 --compress --compress-ratio 0.30

# Test con encoder forzado
python -m wx4 meeting.mp4 --compress --compress-encoder cpu

# Test combinado
python -m wx4 meeting.mp4 --compress --videooutput

# Segunda ejecucion -> skip (ya existe _compressed.mp4)
python -m wx4 meeting.mp4 --compress

# Audio-only debe fallar limpiamente
python -m wx4 audio.m4a --compress
```
