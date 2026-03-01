# Informe 4: Contraste Completo vs Objetivos wx41

Fecha: 2026-02-28

---

## Definicion Completa de los 5 Objetivos

### Objetivo 1: Encadenado de steps
- Capacidad de definir flujo de pasos
- El orden de ejecucion se define declarativamente

### Objetivo 2: Configuracion Declarativa (Modularidad)
- **Activacion/desactivacion** de steps
- **Configuracion de cada step** de forma independiente
- **Orientado a modularidad**: cada step define su propio StepConfig
- **Argumentos configurables**: parametros via config, no hardcodeados
- El pipeline es dinamico: builder decide que steps incluir segun config

### Objetivo 3: Visualizacion en una UI
La UI debe mostrar:
- **Archivo procesado**: archivo actual en proceso
- **Progreso global**: % de steps completados
- **Step**: nombre del step actual
- **Progreso del step**: indicadores de progreso (ej: "transcribing... 45%")
- **Feedback visual**: logs, colores, iconos, progreso en tiempo real

### Objetivo 4: Resumability
- Reanudar desde donde se corto
- Detectar archivos existentes
- No re-ejecutar steps ya completados

### Objetivo 5: Dry Run
- Simular toda la ejecucion sin ejecutar
- Validar configuracion
- Mostrar que pasaria sin hacer I/O real

---

## pipefunc

| Objetivo | Cumple | Detalle |
|----------|--------|---------|
| **Encadenado** | ✅ | DAG automatico por parametros |
| **Declarativo/Modularidad** | ❌ | No tiene StepConfig propio. Parametros sueltos, no hay "step transcribe" con su config. No permite activacion/desactivacion dinamica. |
| **Visualizacion UI** | ⚠️ | Tiene `profile=True` que muestra timing, pero NO muestra: archivo procesado, progreso global, step actual, progreso del step, feedback visual en tiempo real. |
| **Resumability** | ⚠️ | Cache pero no detecta archivos existentes del pipeline |
| **Dry run** | ❌ | No tiene |

**Brecha:** No hay modularidad + UI incompleta.

---

## justpipe

| Objetivo | Cumple | Detalle |
|----------|--------|---------|
| **Encadenado** | ✅ | `@pipe.step(to="x")` |
| **Declarativo/Modularidad** | ❌ | No hay StepConfig. State es unico, no hay config por step. No permite activar/desactivar steps dinamicamente. |
| **Visualizacion UI** | ⚠️ | Tiene eventos (`EventType`) que pueden alimentar una UI externa, pero NO tiene UI propia. No muestra archivo procesado, progreso global, step actual, feedback visual. |
| **Resumability** | ❌ | No tiene |
| **Dry run** | ❌ | No tiene |

**Brecha:** No hay modularidad + no hay UI.

---

## pypyr

| Objetivo | Cumple | Detalle |
|----------|--------|---------|
| **Encadenado** | ✅ | YAML secuencial |
| **Declarativo/Modularidad** | ⚠️ | YAML permite activar/desactivar (`skip`), pero no hay StepConfig Python. Cada step es una funcion, no un modulo con config propio. |
| **Visualizacion UI** | ❌ | No tiene UI. Solo logs en stdout. No muestra archivo procesado, progreso global, step actual, feedback visual. |
| **Resumability** | ❌ | No tiene |
| **Dry run** | ✅ | `pypyr --dry-run` |

**Brecha:** No hay modularidad + no hay UI.

---

## pipelime

| Objetivo | Cumple | Detalle |
|----------|--------|---------|
| **Encadenado** | ✅ | `piper << Stage()` |
| **Declarativo/Modularidad** | ⚠️ | Tiene Stage con parametros, pero no hay StepConfig separado. Parametros van en el constructor del Stage. |
| **Visualizacion UI** | ❌ | No tiene UI propia. Solo CLI con logs. No muestra archivo procesado, progreso global, step actual, feedback visual. |
| **Resumability** | ⚠️ | Cache pero no resume desde archivo existente |
| **Dry run** | ✅ | `--dry-run` |

**Brecha:** No hay modularidad + no hay UI.

---

## pipeco

| Objetivo | Cumple | Detalle |
|----------|--------|---------|
| **Encadenado** | ✅ | Pipes |
| **Declarativo/Modularidad** | ⚠️ | Step tiene atributos como config, pero es parte de la clase. No hay StepConfig separado. |
| **Visualizacion UI** | ❌ | No tiene UI. No muestra archivo procesado, progreso global, step actual, feedback visual. |
| **Resumability** | ❌ | No tiene |
| **Dry run** | ❌ | No tiene |

**Brecha:** API inestable + no hay modularidad + no hay UI.

---

## dynapipeline

| Objetivo | Cumple | Detalle |
|----------|--------|---------|
| **Encadenado** | ✅ | StageGroup + ExecutionStrategy |
| **Declarativo/Modularidad** | ❌ | No hay StepConfig. Stages son clases, parametros en constructor. No hay activacion/desactivacion dinamica. |
| **Visualizacion UI** | ❌ | No tiene UI. No muestra archivo procesado, progreso global, step actual, feedback visual. |
| **Resumability** | ❌ | No tiene |
| **Dry run** | ❌ | No tiene |

**Brecha:** No hay modularidad + no hay UI.

---

## dynaflow

| Objetivo | Cumple | Detalle |
|----------|--------|---------|
| **Encadenado** | ✅ | JSON/ASL |
| **Declarativo/Modularidad** | ⚠️ | JSON declara flujo pero funciones son handlers externos. No hay StepConfig. |
| **Visualizacion UI** | ❌ | No tiene UI. No muestra archivo procesado, progreso global, step actual, feedback visual. |
| **Resumability** | ❌ | No tiene |
| **Dry run** | ❌ | No tiene |

**Brecha:** Paradigma diferente + no hay modularidad + no hay UI.

---

## Custom wx41 (Base)

| Objetivo | Cumple | Detalle |
|----------|--------|---------|
| **Encadenado** | ✅ | NamedStep + Pipeline.run() |
| **Declarativo/Modularidad** | ✅ | **SI tiene StepConfig** (`TranscribeConfig`), **SI tiene activacion/desactivacion** (builder mira settings), **SI tiene configuracion por step**. |
| **Visualizacion UI** | ❌ | No tiene UI. Tiene arquitectura para implementarla: `ctx.outputs`, `ctx.timings`, `step_progress` callback, pero NO muestra: archivo procesado, progreso global, step actual, feedback visual. |
| **Resumability** | ✅ | Check archivos existentes |
| **Dry run** | ❌ | No tiene |

**Brecha:** Faltan visualizacion UI y dry-run. Pero tiene la arquitectura necesaria (outputs dict, timings, observers).

---

## Tabla de Brechas

| Libreria | Declarativo/Modularidad | Visualizacion | Resumability | Dry run |
|----------|------------------------|---------------|--------------|---------|
| pipefunc | ❌ No StepConfig | ❌ | ⚠️ Cache | ❌ |
| justpipe | ❌ No StepConfig | ❌ | ❌ | ❌ |
| pypyr | ⚠️ YAML global | ❌ | ❌ | ✅ |
| pipelime | ⚠️ En Stage | ❌ No tiene | ⚠️ Cache | ✅ |
| pipeco | ⚠️ En clase | ❌ | ❌ | ❌ |
| dynapipeline | ❌ No StepConfig | ❌ | ❌ | ❌ |
| dynaflow | ❌ No StepConfig | ❌ | ❌ | ❌ |
| **Custom wx41** | ✅ **SI** | ❌ | ✅ | ❌ |

---

## Conclusion

**La brecha mas significativa en todas las librerias (excepto custom wx41) es la MODULARIDAD:**

- Ninguna tiene el patron **StepConfig separado** + **Step function recibe config**
- Ninguna permite **activar/desactivar steps dinamicamente** segun configuracion
- Ninguna tiene el concepto de **PipelineContext con outputs dict** donde cada step busca y registra por nombre

**Custom wx41 es la UNICA que cumple:**
- ✅ StepConfig propio
- ✅ Output keys en config
- ✅ Busqueda por nombre en ctx.outputs
- ✅ Registro por nombre en ctx.outputs
- ✅ Activacion/desactivacion via settings
- ✅ Resumability

**Lo que falta en custom wx41:**
- Visualizacion UI (mostrar: archivo procesado, progreso global, step actual, feedback visual)
- Dry run

**Recomendacion:** Mantener custom wx41 y agregar visualizacion + dry-run.
