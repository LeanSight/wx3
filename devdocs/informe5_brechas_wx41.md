# Informe 5: Brechas de wx41 vs Objetivos Completos

Fecha: 2026-02-28

---

## Estado Actual de wx41

Implementacion actual en `wx41/` cumple parcialmente los objetivos. Aqui estan las brechas.

---

## Los 5 Objetivos Completos

### Objetivo 1: Encadenado de steps
- ✅ Implementado: NamedStep + Pipeline.run()

### Objetivo 2: Configuracion Declarativa (Modularidad)
- ✅ StepConfig propio por step
- ✅ output_keys en config
- ✅ Activacion/desactivacion via settings
- ✅ Busqueda por nombre en ctx.outputs
- ✅ Declaracion siempre en Python (dict/dataclass)

### Objetivo 3: Visualizacion en una UI
- ❌ No hay UI
- ❌ No muestra: archivo procesado, progreso global, step actual, feedback visual

### Objetivo 4: Resumability
- ✅ Check archivos existentes
- ⚠️ Falta: Estado persistente entre ejecuciones
- ⚠️ Falta: Resume desde punto de falla

### Objetivo 5: Dry Run
- ❌ No hay modo simulacion
- ❌ No hay validacion de config sin ejecutar

---

## Detalle de Brechas

### Brecha 1: Sin Visualizacion UI

**Estado actual:** No hay forma de ver el estado del pipeline.

**Nueva definicion:** La UI debe mostrar:
- **Archivo procesado**: archivo actual en proceso
- **Progreso global**: % de steps completados
- **Step**: nombre del step actual
- **Progreso del step**: indicadores de progreso
- **Feedback visual**: logs, colores, iconos, progreso en tiempo real

**Que falta:**
- Mostrar archivo procesado actualmente
- Mostrar progreso global (X/Y steps)
- Mostrar step en ejecucion
- Feedback visual en tiempo real
- Mostrar progreso (done/pending/running)

**Como implementar:**
```python
def visualize(ctx: PipelineContext, steps: List[NamedStep], current_step: str = None, progress_percent: float = None):
    print("=== Pipeline Visualization ===")
    
    # Archivo procesado
    print(f"Archivo: {ctx.src}")
    
    # Progreso global
    completed = len(ctx.outputs)
    total = len(steps)
    percent = (completed / total * 100) if total > 0 else 0
    print(f"Progreso: {percent:.0f}% ({completed}/{total})")
    
    # Step actual
    if current_step:
        print(f"Ejecutando: {current_step} ({progress_percent:.0f}%)")
    
    # Lista de steps
    print("\n--- Steps ---")
    for i, step in enumerate(steps):
        if step.name in ctx.outputs:
            status = "✓ done"
        elif step.name == current_step:
            status = "→ running"
        else:
            status = "○ pending"
        print(f"  {status} {step.name}")
```

---

### Brecha 2: Sin Dry Run

**Estado actual:** El pipeline siempre ejecuta.

**Que falta:**
- Flag `--dry-run` o `dry_run=True`
- Simular toda la ejecucion sin I/O
- Validar configuracion antes de ejecutar
- Mostrar que steps ejecutarian y con que parametros

**Como implementar:**
```python
class Pipeline:
    def run(self, ctx, dry_run: bool = False):
        if dry_run:
            for step in self._steps:
                logger.info(f"[DRY RUN] Would execute: {step.name}")
                logger.info(f"[DRY RUN]   config: {step.config}")
                logger.info(f"[DRY RUN]   input: {ctx.outputs}")
            return ctx
        
        # Ejecucion real...
```

---

### Brecha 3: Resumability Incompleto

**Estado actual:** Solo checkea si archivo existe antes de ejecutar.

**Que falta:**
- Estado persistente (sqlite, json, etc)
- Registro de cada step: nombre, status, duracion, archivos generados
- Resume desde el ultimo step completado
- Manejo de errores y reintentos

**Como implementar:**
```python
@dataclass
class StepState:
    name: str
    status: str  # pending, running, done, failed
    started_at: Optional[float]
    finished_at: Optional[float]
    outputs: Dict[str, Path]

class PipelineState:
    steps: Dict[str, StepState]
    
    def save(self, path: Path):
        # Persistir a JSON
        
    def load(self, path: Path) -> "PipelineState":
        # Cargar desde JSON
        
    def get_next_step(self) -> Optional[str]:
        # Encontrar primer step no completado
```

---

## Tabla de Brechas

| Objetivo | Estado | Brecha | Prioridad |
|----------|--------|--------|-----------|
| Encadenado | ✅ Completo | - | - |
| Declarativo | ✅ Completo | Python (no YAML) | - |
| Visualizacion | ❌ Nulo | No hay UI | Alta |
| Resumability | ⚠️ Parcial | Solo check archivos | Alta |
| Dry run | ❌ Nulo | No hay modo simulacion | Alta |

---

## Roadmap para Cerrar Brechas

### Fase 1: Dry Run (Alta prioridad)
- Agregar flag `dry_run` a Pipeline.run()
- Implementar simulacion sin I/O
- Validar configuracion

### Fase 2: Visualizacion (Alta prioridad)
- Agregar metodo `visualize()` que muestre:
  - Arbol de archivos
  - Lista de steps
  - Progreso actual (done/pending)

### Fase 3: Resumability Completo (Media prioridad)
- Implementar PipelineState persistente
- Agregar metadata de cada step
- Implementar resume desde ultimo punto

---

## Conclusion

**wx41 actual cumple 3.5/5 objetivos completamente.**

| Objetivo | Cumplimiento |
|----------|--------------|
| Encadenado | 100% ✅ |
| Declarativo | 100% ✅ (Python) |
| Visualizacion | 0% ❌ |
| Resumability | 50% ⚠️ |
| Dry run | 0% ❌ |

**Promedio: 50%**

Las brechas principales son:
1. Visualizacion UI (0%)
2. Dry run (0%)
3. Resumability completo (50%)

**Recomendacion:** Implementar dry-run y visualizacion primero.
