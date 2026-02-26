# Plan: Brechas de testing UI contra mejores practicas de Rich

## Contexto

Investigacion de mejores practicas (Rich maintainers + comunidad):
- Pattern canonico: `Console(file=StringIO(), force_terminal=True)`
- Alternativa: `Console(record=True)` + `console.export_text()`
- Alternativa: `with console.capture() as capture:`
- Mocks: validos para comportamiento (metodos llamados, columnas)
  pero INSUFICIENTES para verificar output real renderizado
- `force_terminal=True`: obligatorio para que Progress renderice

---

## Estado actual de los tests (verificado 2026-02-26)

Patrones de Console usados hoy:

| Patron | Usos | Captura output? |
|--------|------|-----------------|
| `MagicMock()` para console | mayoria de tests | NO |
| `Console(file=None, force_terminal=True)` | TestCliHierarchicalView | NO — descarta output |
| `Console(file=StringIO())` | NINGUNO | — |
| `Console(record=True)` | NINGUNO | — |

**Ninguno de los tests captura lo que realmente se renderiza.**

---

## Brechas y estado

| Brecha | Descripcion | Estado |
|--------|-------------|--------|
| B1 | Bug de markup no hubiera sido detectado por ningun test | ✗ sin regression test |
| B2 | `Console(file=None)` descarta output — tests no pueden verificar render real | ✗ patron incorrecto aun en uso |
| B3 | `_make_progress()` sin test | ✓ `test_progress_widget_has_bar_column` en test_acceptance.py:590 |
| B4 | S3 sin test de description vacia | ✓ `test_progress_task_has_empty_description` en test_acceptance.py:604 |
| B5 | S1 filename sin test de render | ~ `test_live_display_includes_filename` en test_acceptance.py:570 — verifica `tree.plain`, NO render real con StringIO |

### Detalle B5 (parcial)

`test_live_display_includes_filename` usa `MagicMock()` para console y
verifica `tree.plain`. Cubre que el texto `"audio.mp3"` esta en el arbol.
Lo que NO cubre: que `[bold]audio.mp3[/bold]` no se renderice como literal
— el mismo tipo de bug que tuvimos con `[cyan]`. Para eso hace falta T2.

---

## Tests pendientes

### T2 — Regression test de markup (el unico que realmente falta)

Es el test de mayor valor: si alguien revierte `Text.from_markup` a `Text`,
este test lo detecta inmediatamente.

```python
def test_running_step_renders_colored_icon():
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
    cb._progress_task = None  # sin barra activa -> retorna Text

    tree = cb._render_tree()
    console.print(tree)

    output = buf.getvalue()
    # El tag [cyan] NO debe aparecer como texto literal
    assert "[cyan]" not in output
    # El icono > si debe estar
    assert ">" in output
```

---

## Tests ya implementados (no escribir de nuevo)

- T3 (`_make_progress` columnas): `test_progress_widget_has_bar_column`
  en `test_acceptance.py` — usa instancia real + `.columns`
- T4 (description vacia): `test_progress_task_has_empty_description`
  en `test_acceptance.py` — mock + `call_args`
- T1 (filename en tree): `test_live_display_includes_filename`
  en `test_acceptance.py` — verifica `tree.plain` (suficiente para texto)

### Pendiente menor

`test_on_step_start_shows_step_name` en `test_cli.py:755` tiene nombre
incorrecto — S3 cambio el comportamiento a `description=""` pero el nombre
dice `shows_step_name`. Renombrar a `test_on_step_start_adds_progress_task`
en el mismo slice que T2.

---

## Orden de implementacion

```
T2 (regression markup) + renombrar test_on_step_start -> commit + push
```

Solo queda un slice.

---

## Regla general para UI Rich en este proyecto

> Para comportamiento visual (colores, iconos, formato):
> usar `Console(file=StringIO(), force_terminal=True)` + `console.print(renderable)`.
>
> Para estructura/wiring (es Group, tiene BarColumn, add_task fue llamado):
> mocks son suficientes y mas rapidos.
>
> Cada comportamiento visual nuevo debe tener al menos un test de render.
