# Plan S1a: Cerrar Brechas de UI + Dry Run

Fecha: 2026-03-01

Referencia: devdocs/standard-atdd-tdd.md

---

## Estado Actual S1

| Objetivo | Estado | Siguiente |
|----------|--------|-----------|
| Encadenado | ✅ Listo | - |
| Declarativo/Modularidad | ✅ Listo | - |
| Visualizacion UI | ❌ Pendiente | Implementar |
| Resumability | ⚠️ Parcial | Mejorar |
| Dry run | ❌ Pendiente | Implementar |

---

## Metodologia (standard-atdd-tdd.md)

Seguir ciclo:
1. AT primero (RED)
2. Unit tests (RED)
3. Produccion minima (GREEN)
4. Commit + Push inmediato
5. Refactor si necesario

---

## Slice 1: Dry Run

### 1.1 AT (RED)

```python
# wx41/tests/test_dry_run.py
def test_dry_run_no_execution(tmp_path):
    """Dry run no debe ejecutar steps, solo mostrar que haria."""
    audio = tmp_path / "test.m4a"
    audio.touch()
    
    config = PipelineConfig(
        settings={"transcribe": TranscribeConfig(backend="whisper")}
    )
    
    orchestrator = MediaOrchestrator(config, [])
    ctx = orchestrator.run(audio, dry_run=True)
    
    # No debe generar archivos
    assert not (tmp_path / "transcript_txt").exists()
    assert not (tmp_path / "transcript_json").exists()
    
    # Debe marcar como dry run
    assert ctx.dry_run is True
```

### 1.2 Produccion minima

En `context.py`:
```python
@dataclass(frozen=True)
class PipelineContext:
    src: Path
    force: bool = False
    outputs: Dict[str, Path] = field(default_factory=dict)
    timings: Dict[str, float] = field(default_factory=dict)
    step_progress: Optional[Callable] = None
    dry_run: bool = False  # AGREGAR
```

En `pipeline.py`:
```python
def run(self, ctx: PipelineContext, dry_run: bool = False) -> PipelineContext:
    ctx = dataclasses.replace(ctx, dry_run=dry_run)
    
    if dry_run:
        self._log_dry_run(ctx)
        return ctx
    
    # Ejecucion normal...
```

---

## Slice 2: Visualizacion UI con Rich

### 2.1 AT (RED)

```python
# wx41/tests/test_ui_visualization.py
def test_ui_shows_progress(tmp_path):
    """UI debe mostrar: archivo, progreso global, step actual."""
    audio = tmp_path / "test.m4a"
    audio.write_bytes(b"fake audio")
    
    captured = io.StringIO()
    
    config = PipelineConfig(settings={})
    orchestrator = MediaOrchestrator(config, [])
    
    # Pipe progress a StringIO para capturar
    ctx = orchestrator.run(
        audio, 
        progress=ProgressConsole(captured)
    )
    
    output = captured.getvalue()
    
    # Verificar elementos
    assert "test.m4a" in output
    assert any(s in output for s in ["normalize", "transcribe"])
    assert "%" in output or "progress" in output.lower()
```

### 2.2 Unit Test (RED)

```python
# wx41/tests/test_progress.py
def test_progress_console_shows_step():
    console = ProgressConsole(io.StringIO())
    
    console.on_step_start("transcribe")
    console.on_step_progress("transcribe", 50)
    console.on_step_end("transcribe")
    
    output = console.get_output()
    assert "transcribe" in output
    assert "50" in output
```

### 2.3 Produccion minima

```python
# wx41/ui/progress.py
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

class ProgressConsole:
    def __init__(self, console):
        self.console = console
        self.progress = None
        self.tasks = {}
    
    def on_pipeline_start(self, steps, ctx):
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold]{task.description}"),
            TimeElapsedColumn(),
            console=self.console
        )
        self.progress.__enter__()
    
    def on_step_start(self, name):
        if self.progress:
            self.tasks[name] = self.progress.add_task(name, total=100)
    
    def on_step_progress(self, name, percent):
        if self.progress and name in self.tasks:
            self.progress.update(self.tasks[name], completed=percent)
    
    def on_step_end(self, name):
        if self.progress and name in self.tasks:
            self.progress.update(self.tasks[name], completed=100)
            self.tasks[name] = None
    
    def on_pipeline_end(self, ctx):
        if self.progress:
            self.progress.__exit__(None, None, None)
```

---

## Slice 3: Resumability Mejorado

### 3.1 AT (RED)

```python
# wx41/tests/test_resume.py
def test_resume_from_existing_output(tmp_path):
    """Si output existe, no debe re-ejecutar."""
    audio = tmp_path / "test.m4a"
    audio.write_bytes(b"fake")
    
    # Output previo existe
    prev_output = tmp_path / "transcript_txt"
    prev_output.write_text("previous result")
    
    config = PipelineConfig(force=False)
    orchestrator = MediaOrchestrator(config, [])
    
    # Ejecutar con resume
    ctx = orchestrator.run(audio, resume=True)
    
    # Debe usar el output existente
    assert ctx.outputs["transcript_txt"].read_text() == "previous result"
    
    # No debe haber ejecutado (timings vacio o solo steps completados)
    assert "transcribe" not in ctx.timings
```

### 3.2 Produccion minima

```python
def run(self, ctx, resume=False):
    steps_to_run = []
    
    for step in self._steps:
        if resume:
            # Check si output existe
            output_key = getattr(step.config, 'output_keys', [step.name])[0]
            if output_key in ctx.outputs and ctx.outputs[output_key].exists():
                continue  # Skip, ya existe
        
        steps_to_run.append(step)
    
    # Ejecutar solo steps faltantes
    for step in steps_to_run:
        ctx = step.fn(ctx)
    
    return ctx
```

---

## Slice 4: Control+C (Graceful Interruption)

### 4.1 AT (RED)

```python
# wx41/tests/test_interrupt.py
def test_ctrl_c_graceful(tmp_path):
    """Ctrl+C debe guardar estado antes de salir."""
    audio = tmp_path / "test.m4a"
    audio.write_bytes(b"fake")
    
    config = PipelineConfig()
    orchestrator = MediaOrchestrator(config, [])
    
    # Simular Ctrl+C durante ejecucion
    ctx = orchestrator.run(audio, interrupt_at="transcribe")
    
    # Debe guardar estado
    state_file = tmp_path / ".wx41_state.json"
    assert state_file.exists()
    
    # ctx debe tener flag de interrupcion
    assert ctx.interrupted is True
    
    # Los outputs completados deben existir
    # (el step actual puede no haber terminado)
```

### 4.2 Produccion minima

```python
# ui/interrupt.py
import signal
import sys

class InterruptHandler:
    def __init__(self, pipeline, ctx):
        self.pipeline = pipeline
        self.ctx = ctx
        self.interrupted = False
    
    def handle(self, signum, frame):
        print("\n[yellow]Interruption detected. Saving state...[/yellow]")
        self.interrupted = True
        
        # Guardar estado para resume
        self._save_state()
        
        # Limpiar UI
        self.pipeline.cleanup()
        
        sys.exit(0)
    
    def _save_state(self):
        state = {
            "outputs": {k: str(v) for k, v in self.ctx.outputs.items()},
            "timings": self.ctx.timings,
            "src": str(self.ctx.src),
        }
        Path(".wx41_state.json").write_text(json.dumps(state))

def run_with_interrupt_handling(pipeline, ctx):
    handler = InterruptHandler(pipeline, ctx)
    
    # Registrar handler para SIGINT (Ctrl+C)
    signal.signal(signal.SIGINT, handler.handle)
    
    return pipeline.run(ctx)
```

---

## Tabla de Slices

| Slice | Objetivo | Tipo | Archivos a crear/modificar |
|-------|----------|------|---------------------------|
| 1 | Dry Run | AT + Prod | test_dry_run.py, context.py, pipeline.py |
| 2 | UI | AT + Unit + Prod | test_ui.py, test_progress.py, ui/progress.py |
| 3 | Resumability | AT + Prod | test_resume.py, pipeline.py |
| 4 | Control+C | AT + Prod | test_interrupt.py, ui/interrupt.py |

---

## Orden de implementacion (One-Piece-Flow)

1. **Slice 1**: Dry Run
   - Escribir AT → RED
   - Escribir produccion minima → GREEN
   - Commit + Push

2. **Slice 2**: UI
   - Escribir AT → RED
   - Escribir Unit Test → RED
   - Escribir produccion minima → GREEN
   - Commit + Push

3. **Slice 3**: Resumability
   - Escribir AT → RED
   - Escribir produccion minima → GREEN
   - Commit + Push

4. **Slice 4**: Control+C
   - Escribir AT → RED
   - Escribir produccion minima → GREEN
   - Commit + Push

---

## Criterios de aceptacion

### Dry Run
- [ ] `dry_run=True` no ejecuta steps
- [ ] No genera archivos de output
- [ ] `ctx.dry_run` esta en True
- [ ] Muestra que steps ejecutaria

### UI
- [ ] Muestra archivo procesado
- [ ] Muestra progreso global (X/Y)
- [ ] Muestra step actual
- [ ] Muestra progreso del step (%)
- [ ] Feedback visual (spinner, barra)

### Resumability
- [ ] Si output existe, no re-ejecuta
- [ ] Si `force=True`, siempre ejecuta
- [ ] Si `resume=True`, usa outputs existentes

### Control+C
- [ ] Ctrl+C guarda estado antes de salir
- [ ] Genera archivo `.wx41_state.json`
- [ ] ctx.interrupted esta en True
- [ ] Los outputs completados se сохраняют
- [ ] Se puede resume desde el estado guardado
