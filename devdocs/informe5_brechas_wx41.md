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
- ⚠️ Falta: Configuracion via YAML/JSON (solo dict)

### Objetivo 3: Visualizacion en una UI
- ❌ No hay UI
- ❌ No hay grafico interactivo

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

**Estado actual:** No hay forma de ver el pipeline graficamente.

**Que falta:**
- UI para mostrar steps y conexiones
- Indicador de progreso en tiempo real
- Estado de cada step (pending, running, done, failed)

**Alternativas para implementar:**
- Graphviz para generar imagen estatica
- Rich/TUI para terminal interactiva
- Flask/FastAPI para web UI
- Integracion con herramienta externa

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

### Brecha 4: Configuracion Solo Dict (no YAML/JSON)

**Estado actual:** Solo acepta dict en Python.

**Que falta:**
- Cargar configuracion desde archivo YAML
- Cargar configuracion desde archivo JSON
- Validacion de schema

**Como implementar:**
```python
def load_config_from_yaml(path: Path) -> PipelineConfig:
    import yaml
    data = yaml.safe_load(path.read_text())
    
    settings = {}
    for step_name, step_config in data.get("steps", {}).items():
        if step_name == "transcribe":
            settings[step_name] = TranscribeConfig(**step_config)
        # ...
    
    return PipelineConfig(
        force=data.get("force", False),
        settings=settings
    )
```

---

## Tabla de Brechas

| Objetivo | Estado | Brecha | Prioridad |
|----------|--------|--------|-----------|
| Encadenado | ✅ Completo | - | - |
| Declarativo | ⚠️ Parcial | Solo dict, no YAML/JSON | Media |
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
- Agregar metodo `visualize()` que genere grafo
- Opcional: UI con Rich/TUI

### Fase 3: Resumability Completo (Media prioridad)
- Implementar PipelineState persistente
- Agregar metadata de cada step
- Implementar resume desde ultimo punto

### Fase 4: YAML/JSON Config (Baja prioridad)
- Agregar loader desde archivo
- Validacion de schema

---

## Conclusion

**wx41 actual cumple 2.5/5 objetivos completamente.**

| Objetivo | Cumplimiento |
|----------|--------------|
| Encadenado | 100% |
| Declarativo | 80% |
| Visualizacion | 0% |
| Resumability | 50% |
| Dry run | 0% |

**Promedio: 46%**

Las brechas principales son:
1. Visualizacion UI (0%)
2. Dry run (0%)
3. Resumability completo (50%)

**Recomendacion:** Implementar dry-run y visualizacion primero.
