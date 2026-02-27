# UI Rich: Test-First Best Practices

Guia extraida de la experiencia en wx4 + investigacion de la suite de
tests de Rich (Textualize) + comunidad 2025-2026.

---

## Dos niveles de test, dos herramientas distintas

| Nivel | Que verifica | Herramienta |
|-------|-------------|-------------|
| Estructura / wiring | Es Group? Tiene BarColumn? add_task fue llamado? | Mock / inspect |
| Output visual | Que ve el usuario en el terminal | `Console(file=StringIO())` |

Usar el nivel equivocado da falsa cobertura.

---

## Nivel 1: Estructura y wiring (mocks)

Util para verificar:
- Tipo de retorno (`isinstance(result, Group)`)
- Columnas de Progress (`isinstance(c, BarColumn) for c in p.columns`)
- Metodos llamados (`progress.add_task.assert_called()`)
- Argumentos (`call_args.args[0] == ""`)

```python
def test_render_tree_returns_group_when_step_active():
    progress = MagicMock(spec=Progress)
    progress.add_task = MagicMock(return_value=42)
    cb = RichProgressCallback(MagicMock(), progress)
    cb._step_names = ["enhance"]
    cb._step_states = {"enhance": "running"}
    cb._progress_task = 42

    result = cb._render_tree()

    assert isinstance(result, Group)
    assert progress in result.renderables
```

```python
def test_make_progress_has_bar_column():
    from rich.progress import BarColumn
    from wx4.cli import _make_progress

    p = _make_progress(MagicMock())

    assert any(isinstance(c, BarColumn) for c in p.columns)
```

**Limitacion**: mocks no detectan bugs de markup.
`Text("[cyan]>[/cyan]")` y `Text.from_markup("[cyan]>[/cyan]")` tienen
el mismo `.plain` = `">"` pero renderizan diferente en el terminal.

---

## Nivel 2: Output visual (StringIO)

Pattern canonico de la suite de Rich:

```python
from io import StringIO
from rich.console import Console

buf = StringIO()
console = Console(file=buf, force_terminal=True, width=80)
```

- `file=buf`: captura el output en memoria en vez de escribirlo al terminal
- `force_terminal=True`: Rich renderiza colores y Progress aunque no detecte TTY
- `width=80`: fija el ancho para evitar variacion por terminal
- Leer output: `buf.getvalue()`

### Ejemplo: regression test de markup

```python
def test_running_step_renders_colored_icon_not_literal_markup():
    from io import StringIO
    from rich.console import Console
    from wx4.cli import RichProgressCallback
    from wx4.context import PipelineContext

    buf = StringIO()
    console = Console(file=buf, force_terminal=True, width=80)
    progress = MagicMock()
    progress.add_task = MagicMock(return_value=1)
    cb = RichProgressCallback(console, progress)

    ctx = PipelineContext(src=Path("/test/audio.mp3"))
    cb.on_pipeline_start(["enhance"], ctx)
    cb._step_states["enhance"] = "running"
    cb._progress_task = None

    tree = cb._render_tree()
    console.print(tree)

    output = buf.getvalue()
    assert "[cyan]" not in output   # markup literal = bug
    assert ">" in output            # icono presente
```

Este test hubiera detectado el bug `Text()` vs `Text.from_markup()`
antes de llegar al terminal.

### Alternativas equivalentes

```python
# Con record=True
console = Console(record=True, force_terminal=True, width=80)
console.print(tree)
output = console.export_text()

# Con capture()
with console.capture() as capture:
    console.print(tree)
output = capture.get()
```

---

## Anti-patrones

### Console(file=None) — output descartado silenciosamente

```python
# MAL: file=None descarta todo, el test no puede afirmar sobre output
console = Console(file=None, force_terminal=True)
cb = RichProgressCallback(console, progress)
cb.on_pipeline_start(["enhance"], ctx)
# no hay forma de verificar que se renderizo correctamente
```

### MagicMock() para console en tests de render visual

```python
# MAL para tests de colores/formato:
console = MagicMock()
cb = RichProgressCallback(console, progress)
# console.print() es un mock que no hace nada
# ningun bug de markup sera detectado
```

Mock para console es aceptable en tests de comportamiento (wiring),
pero no en tests de output visual.

### tree.plain no detecta markup literal

```python
# INSUFICIENTE para verificar colores:
tree = cb._render_tree()
assert ">" in tree.plain   # pasa tanto con Text() como con Text.from_markup()
# no detecta si [cyan] se muestra como texto literal
```

`.plain` extrae el texto sin formato. Es correcto para verificar
contenido de texto (filenames, porcentajes, nombres de steps),
pero no detecta bugs de markup.

---

## Regla de oro

> **Texto**: `tree.plain` es suficiente.
> **Colores / formato**: `Console(file=StringIO(), force_terminal=True)`.
> **Estructura**: mocks.

Un test de render por comportamiento visual nuevo es obligatorio.
Si el comportamiento involucra markup Rich (`[cyan]`, `[bold]`, `[dim]`),
el test debe usar StringIO.

---

## Cuando usar cada patron

| Comportamiento a testear | Patron |
|--------------------------|--------|
| `_render_tree()` retorna `Group` cuando step activo | mock + `isinstance` |
| `Progress` tiene `BarColumn` | instancia real + `.columns` |
| `add_task` llamado con description vacia | mock + `call_args` |
| Filename aparece en el arbol | `tree.plain` o StringIO |
| Icono `>` no se muestra como `[cyan]>[/cyan]` | StringIO obligatorio |
| Step completo muestra icono verde | StringIO obligatorio |
| Barra de progreso avanza visualmente | StringIO + `force_terminal=True` |

---

## Nota sobre Live y Progress en tests

`Live` arrancado con `live.start()` inicia un thread de refresh.
Siempre llamar `live.stop()` al final del test para evitar leaks:

```python
cb.on_pipeline_start(["enhance"], ctx)
try:
    # ... test ...
finally:
    if cb._live:
        cb._live.stop()
```

O usar `on_pipeline_end(ctx)` que llama `stop()` internamente.

`Progress` embebido en `Live` no necesita `start()`/`stop()` propio
— el `Live` gestiona su ciclo de vida.
