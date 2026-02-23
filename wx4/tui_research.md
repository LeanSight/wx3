# TUI Research: Python Pipelines CLI (Feb 2026)

## Landscape actual

| Lib      | Version actual | Rol                        | Autor        |
|----------|---------------|----------------------------|--------------|
| Rich     | 14.1.0+       | Formateo, Progress, Table  | Textualize   |
| Textual  | 1.x           | Framework TUI interactivo  | Textualize   |
| Typer    | 0.12+         | CLI parsing (encima Click) | tiangolo     |

Textual esta construido ENCIMA de Rich. Ambos son del mismo equipo (Textualize).

---

## Decision: Rich vs Textual para nuestro pipeline

### Usa Rich cuando:
- El CLI es non-interactive: el usuario lanza, espera, ve resultado
- Necesitas Progress bars, tablas, colores
- El pipeline corre de forma secuencial o en threads
- No necesitas input del usuario DURANTE la ejecucion

### Usa Textual cuando:
- Necesitas widgets interactivos: botones, checkboxes, inputs
- Quieres un "dashboard" que el usuario navega con teclado/mouse
- La app tiene eventos: key press, mouse click, reactive state
- Modelo async + event-driven (como una web app en terminal)

**Conclusion para wx4:** Rich es el standard correcto. Nuestro pipeline
es fire-and-forget: el usuario da el archivo, espera, ve el resultado.
Textual seria over-engineering para este caso.

---

## Patterns de Rich para pipelines (standard 2026)

### Pattern 1: track() - pipeline lineal simple

```python
from rich.progress import track

steps = [extract, normalize, enhance, encode, transcribe, srt]
for step in track(steps, description="Processing..."):
    step(ctx)
```

Pro: 1 linea. Contra: no muestra nombre del step actual.

---

### Pattern 2: Progress con tasks nombrados - el standard

```python
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

with Progress(
    SpinnerColumn(),
    TextColumn("[progress.description]{task.description}"),
    TimeElapsedColumn(),
) as progress:
    task = progress.add_task("Extracting audio...", total=None)  # indeterminate
    ctx = extract_to_wav(ctx)
    progress.update(task, description="Normalizing LUFS...", completed=1, total=1)
    ctx = normalize_lufs(ctx)
    # etc.
```

`total=None` = barra pulsante (indeterminate) mientras no sabemos cuanto tarda.
Muy apropiado para steps con duracion variable (ClearVoice, AssemblyAI).

---

### Pattern 3: Progress.console.print - logs encima de la barra

```python
with Progress(...) as progress:
    task = progress.add_task("Enhancing...", total=None)
    progress.console.print(f"[dim]Loading {model_name}...")
    cv = ClearVoice(...)
    progress.console.print("[green]Model loaded.")
    apply_clearvoice(ctx)
    progress.update(task, completed=1, total=1)
```

Los prints aparecen ENCIMA de la barra sin romperla.
Reemplaza el `console.print(f"Loading {_CV_MODEL}...")` actual.

---

### Pattern 4: Live + Group - multiples Progress en pantalla

Para pipelines con steps en paralelo o con sub-tasks visibles simultaneamente:

```python
from rich.live import Live
from rich.console import Group

overall = Progress(...)
step_progress = Progress(...)

with Live(Group(overall, step_progress)):
    ...
```

Util si en el futuro procesamos multiples archivos en paralelo.

---

### Pattern 5: transient=True - limpia la barra al terminar

```python
with Progress(transient=True) as progress:
    ...
# Al salir del context manager, la barra desaparece.
# Solo queda visible el Summary table final.
```

Clean output: el usuario ve solo el resultado, no el historial de barras.
Muy comun en CLIs como pip, uv, rye.

---

## Columnas recomendadas para nuestro pipeline

```python
Progress(
    SpinnerColumn(),                          # animacion mientras trabaja
    TextColumn("[bold]{task.description}"),   # nombre del step
    BarColumn(),                              # barra (si total conocido)
    TimeElapsedColumn(),                      # cuanto lleva
)
```

Nota: NO usar MofNCompleteColumn ni TimeRemainingColumn para steps
con duracion variable (enhance, transcribe) - no tienen sentido sin total real.

---

## Integracion con Typer (standard actual)

Typer tiene `typer.progressbar()` pero es wrapper basico de Click.
El estandar 2026 es usar Rich Progress directamente dentro del comando Typer:

```python
@app.command()
def main(ctx: typer.Context, files: Optional[List[str]] = ...) -> None:
    with Progress(SpinnerColumn(), TextColumn("{task.description}"), ...) as progress:
        for file_str in files:
            task = progress.add_task(f"[cyan]{Path(file_str).name}", total=6)
            ctx = pipeline.run(ctx, progress=progress, task=task)
```

O pasar el `progress` al pipeline como dependencia inyectada.

---

## ASCII compliance (CLAUDE.md constraint)

Rich usa Unicode box-drawing por defecto. Para cp1252 Windows:

```python
from rich import box
Table(box=box.ASCII)          # ya implementado en wx4/cli.py
Progress(...)                 # SpinnerColumn usa ASCII spinners por defecto: OK
Console(force_terminal=True)  # si el output se redirige a archivo
```

SpinnerColumn usa `|/-\` por defecto en entornos sin Unicode - safe.
Verificar con `.isascii()` en tests (ya tenemos test_output_contains_no_non_ascii).

---

## Veredicto para wx4 v2

El pipeline actual muestra `console.print(f"Loading {_CV_MODEL}...")` y luego
la tabla final. La mejora estandar seria:

1. Reemplazar prints sueltos por `Progress` con SpinnerColumn
2. Usar `transient=True` para que la barra desaparezca al terminar
3. Conservar el Summary Table al final (ya existe, ya es ASCII)
4. Inyectar `progress` en el pipeline como parametro opcional de cada step

Esto NO requiere Textual. Rich Progress es el estandar pythonic para
pipelines CLI fire-and-forget en 2026.

---

## Fuentes

- [Rich Progress Display docs](https://rich.readthedocs.io/en/latest/progress.html)
- [Building CLI Tools with Typer and Rich (Jan 2026)](https://dasroot.net/posts/2026/01/building-cli-tools-with-typer-and-rich/)
- [Python Textual: Building Modern TUIs (Jan 2026)](https://medium.com/@shouke.wei/python-textual-building-modern-terminal-user-interfaces-with-pure-python-9c864909fe22)
- [Rich vs Textual comparison](https://nccastaff.bournemouth.ac.uk/jmacey/msc/PipeLineAndTD/motw/textual/)
- [Rich GitHub](https://github.com/Textualize/rich)
