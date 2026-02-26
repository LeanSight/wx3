# Plan: UI Progress - 3 slices

Metodologia: ATDD + TDD + One-Piece-Flow (ver plan-atdd-tdd.md).

---

## Estado actual verificado (pre-plan)

### S1 - Nombre de archivo
- Produccion: `_current_file` se guarda en `on_pipeline_start` (linea 148)
  pero `_render_tree()` NUNCA lo usa -> NO implementado
- Test existente: `test_callback_receives_file_name_on_pipeline_start` verifica
  `cb._current_file == src` (almacenamiento, no renderizado) -> INSUFICIENTE
- Conclusion: brecha real, slice necesario

### S2 - BarColumn
- Imports: `BarColumn` y `TimeElapsedColumn` YA estan importados (lineas 15-20)
  pero son imports HUERFANOS - no se usan en ninguna parte
- Produccion: `Progress(SpinnerColumn(), TextColumn("{task.description}"), ...)`
  sin BarColumn -> NO implementado
- Test existente: ninguno verifica las columnas del Progress
- Conclusion: brecha real, slice necesario

### S3 - Description redundante
- Produccion: `self._progress.add_task(f"  {name}", total=100)` -> usa nombre del step
- Test existente: `test_on_step_start_shows_step_name` solo llama
  `progress.add_task.assert_called()` - NO verifica la descripcion especifica
- Si se cambia la descripcion a "", ese test SIGUE PASANDO sin cambios
- El nombre del test queda incorrecto -> renombrar en el mismo slice
- Conclusion: brecha real, slice necesario

---

## Slice 1: Nombre de archivo en header del Live

**Una sola cosa**: `_render_tree()` incluye `_current_file.name` como primera linea.

**Salida esperada en terminal:**
```
audio.mp3
  x cache_check
  > enhance 45%
  o transcribe
```

### AT RED (test_acceptance.py)

Nuevo test: simula pipeline con 2 steps, captura el renderable del Live,
verifica que el nombre del archivo esta en el texto renderizado.

```python
def test_live_display_includes_filename(tmp_path):
    # on_pipeline_start con src="audio.mp3"
    # _render_tree().plain contiene "audio.mp3"
```

### Unit RED (test_cli.py - agregar a TestRichProgressCallbackPercentageDisplay)

```python
def test_render_tree_includes_current_file_name():
    # cb._current_file = Path("/test/audio.mp3")
    # cb._step_names = ["enhance"]
    # tree = cb._render_tree()
    # "audio.mp3" in tree.plain
```

### Produccion minima

En `_render_tree()`, agregar antes del loop:
```python
if self._current_file:
    lines.append(f"[bold]{self._current_file.name}[/bold]")
```

### Tests existentes a verificar (no deben regresar a RED)

- `test_render_tree_shows_percentage_for_running_step`: llama `on_pipeline_start`
  con `ctx.src = Path("/test/audio.mp4")` -> `_current_file` se seteara.
  Despues de S1, `tree.plain` incluira "audio.mp4". La asercion `"45%" in tree.plain`
  SIGUE PASANDO. OK.

- `test_pending_step_shows_no_percentage`: mismo escenario. `_current_file` sera
  Path("/test/audio.mp4"). "%" no esta en "audio.mp4". La asercion
  `"%" not in tree.plain` SIGUE PASANDO. OK.

- `test_render_tree_returns_text_when_no_active_task` y otros en
  TestRichProgressCallbackProgressWidget: no setean `_current_file` (= None).
  El `if self._current_file:` lo saltea. SIGUEN PASANDO. OK.

---

## Slice 2: BarColumn en Progress

**Una sola cosa**: Progress incluye BarColumn + TimeElapsedColumn para
visualizar progreso determinista de compress/enhance.

**Salida esperada:**
```
audio.mp3
  > compress 45%
  [spinner] [=========>   ] 45%  0:00:12
```

### Diseno: extraer `_make_progress()` como helper testeable

Para evitar testear a traves de `main()` (costoso de mockear), extraer la
construccion del Progress a una funcion modulo-nivel:

```python
def _make_progress(console: Console) -> Progress:
    return Progress(
        SpinnerColumn(),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%%"),
        TimeElapsedColumn(),
        console=console,
    )
```

Y en `main()`: `progress = _make_progress(console)`

### AT RED (test_acceptance.py)

```python
def test_progress_widget_has_bar_column():
    from rich.progress import BarColumn
    from wx4.cli import _make_progress
    from unittest.mock import MagicMock
    p = _make_progress(MagicMock())
    assert any(isinstance(c, BarColumn) for c in p.columns)
```

### Unit RED (test_cli.py - nueva clase TestMakeProgress)

```python
def test_make_progress_has_bar_column():
    from rich.progress import BarColumn
    from wx4.cli import _make_progress
    p = _make_progress(MagicMock())
    assert any(isinstance(c, BarColumn) for c in p.columns)

def test_make_progress_has_time_elapsed_column():
    from rich.progress import TimeElapsedColumn
    from wx4.cli import _make_progress
    p = _make_progress(MagicMock())
    assert any(isinstance(c, TimeElapsedColumn) for c in p.columns)
```

### Produccion

1. Agregar `_make_progress(console)` en `cli.py`
2. En `main()`: `progress = _make_progress(console)`
3. Los imports huerfanos `BarColumn` y `TimeElapsedColumn` pasan a ser usados

### Tests existentes a verificar

- Todos los tests que mockean `progress = MagicMock(spec=Progress)` no
  se ven afectados (no instancian el Progress real). SIGUEN PASANDO. OK.

---

## Slice 3: Description vacia en task (eliminar redundancia)

**Una sola cosa**: `add_task` recibe `""` como descripcion, no el nombre del step.

**Salida esperada:**
```
audio.mp3
  > compress 45%
  [spinner] [=========>   ] 45%  0:00:12   <- sin "compress" antes de la barra
```

### AT RED (test_acceptance.py)

```python
def test_progress_task_has_empty_description():
    # cb.on_step_start("compress", ctx)
    # progress.add_task llamado con "" como primer argumento
```

### Unit RED (test_cli.py)

```python
def test_on_step_start_adds_task_with_empty_description():
    cb.on_step_start("compress", ctx)
    call_args = progress.add_task.call_args
    assert call_args.args[0] == ""
```

### Produccion

```python
# on_step_start:
self._progress_task = self._progress.add_task("", total=100)
```

### Tests existentes a actualizar

- `test_on_step_start_shows_step_name` (linea 696): solo llama
  `progress.add_task.assert_called()` - NO verifica la descripcion ->
  TEST SIGUE PASANDO sin cambios, pero el nombre es incorrecto.
  RENOMBRAR a `test_on_step_start_adds_progress_task` en este slice.
  Cambio de comportamiento intencional -> actualizar nombre del test.

---

## Orden de ejecucion

```
S1 (filename en _render_tree) -> commit + push
S2 (BarColumn via _make_progress) -> commit + push
S3 (description vacia) -> commit + push
```

S2 y S3 son independientes entre si. S1 es independiente de ambos.

---

## Riesgo real identificado

En S2: para steps sin progreso determinista (`transcribe_step` NO llama
`step_progress`), el task queda con `completed=0, total=100`.
Rich con `BarColumn` muestra una barra vacia `[          ]  0%`.
Esto es visualmente correcto (indica que no hay info de progreso) pero
puede verse raro. Alternativa: usar `BarColumn(style="bar.back")` o
`total=None` para modo indeterminate. Decidir al implementar S2.
