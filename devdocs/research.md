# Research: Pipeline Libraries para wx41

Fecha: 2026-02-28

## Objetivo

Investigar 13 librerías de pipelines en Python para determinar cuál es la más adecuada para cumplir los 5 objetivos de wx41:

1. **Encadenado de steps**
2. **Configuración declarativa de steps**
3. **Visualización en una UI**
4. **Resumability**
5. **Dry run**

## Librerías a Investigar

| # | Libreria | Tipo | Status |
|---|----------|------|--------|
| 1 | pipefunc | DAG function pipeline | Implementado |
| 2 | justpipe | Async orchestration | Implementado |
| 3 | pypyr | YAML declarative | Implementado |
| 4 | pipelime | Data pipeline + CLI | Implementado |
| 5 | pipeco | Pydantic-based | Pendiente |
| 6 | pydiverse.pipedag | Data orchestration | Pendiente |
| 7 | dynapipeline | Async pipeline | Pendiente |
| 8 | dynaflow | ASL-based | Pendiente |
| 9 | nextflow | Bioinformatics | Pendiente |
| 10 | flyte | ML pipelines | Pendiente |
| 11 | snakemake | Workflows | Pendiente |
| 12 | dagster | Data orchestrator | Pendiente |
| 13 | prefect | Dataflow | Pendiente |

---

## Plan de Investigación

### Fase 1: Instalación y Hello World
- Instalar librería
- Crear ejemplo mínimo funcional
- Verificar que corre sin errores

### Fase 2: Implementar S1 (Walking Skeleton)
Implementar el mismo caso de uso en cada librería:

```python
# Caso S1: Pipeline con normalize + transcribe
# Entrada: audio.m4a
# Salida: transcript.txt, timestamps.json
```

Criterios de implementación:
- Usar TranscribeConfig con backend configurable
- Manejar outputs como archivos en disco
- Integrar con transcribe_assemblyai o transcribe_whisper

### Fase 3: Evaluar contra Objetivos wx41

| Objetivo | Criterio de evaluación |
|----------|------------------------|
| Encadenado | ¿La librería permite encadenar steps? ¿Cómo se define el flujo? |
| Declarativo | ¿Soporta configuración en YAML/JSON? ¿Cómo se activan/desactivan steps? |
| Visualización | ¿Tiene UI o visualización del pipeline? |
| Resumability | ¿Puede reanudar si se interrumpe? ¿Tiene cache? |
| Dry run | ¿Soporta simular sin ejecutar? |

### Fase 4: Captar Patrones Pythonic

Documentar patrones de diseño observados:

- **Patrones de encadenado**: Decoradores, clases, funciones, YAML
- **Patrones de configuración**: dataclasses, Pydantic, dict, YAML
- **Patrones de state management**: Context, State, PipelineContext
- **Patrones de I/O**: Archivos, streams, memoria
- **Patrones de error handling**: Retry, catch, recovery

---

## Criterios de Evaluación

### Scorecard por Librería

```
Libreria: ___________

Encadenado (0-5): ____
  - ¿Soporta steps?
  - ¿Definición declarativa?
  - ¿DAG automático?

Declarativo (0-5):
  - ¿YAML/JSON?
  - ¿Activación dinámica de steps?
  - ¿Configuración externo?

Visualización (0-5):
  - ¿UI integrada?
  - ¿Gráfico del pipeline?
  - ¿Logging estructurado?

Resumability (0-5):
  - ¿Cache automático?
  - ¿Resume desde checkpoint?
  - ¿Detección de archivos existentes?

Dry run (0-5):
  - ¿Soporte nativo?
  - ¿Simulación de ejecución?
  - ¿Validación de config?

Pythonicidad (0-5):
  - ¿Type hints?
  - ¿Idiomatico?
  - ¿Zero/minimal deps?

TOTAL: ____/30
```

---

## Resultados Esperados

1. **Tabla comparativa** de las 13 librerías
2. **Patrones de diseño** identificados como candidatos para wx41
3. **Recomendación** de librería o implementación custom
4. **Roadmap** para implementar objetivos faltantes

---

## Próximos Pasos

1. Completar implementación S1 en pipefunc, justpipe, pypyr, pipelime (hecho)
2. Implementar S1 en pipeco, pydiverse.pipedag, dynapipeline, dynaflow
3. Evaluar cada librería contra el scorecard
4. Documentar patrones pythonic encontrados
5. Redactar recomendación final
