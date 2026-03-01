# Comparacion: Implementaciones S1 vs Objetivos wx41

## Objetivos wx41 (plan_wx41.md)

1. Forma mas idiomática y pythónica en 2026
2. Encadenado de steps
3. Configuración declarativa de steps
4. Visualización en una UI
5. Resumability (retoma si se detiene)
6. Dry run (simular ejecución)

---

## Tabla Comparativa (13 Librerias)

| Objetivo | Custom | pipefunc | justpipe | pypyr | pipelime | pipeco | dynapipeline | dynaflow | dagster | prefect | nextflow | flyte | snakemake |
|----------|--------|----------|----------|-------|----------|--------|--------------|----------|---------|---------|----------|-------|------------|
| **Encadenado** | Si | Si | Si | Si | Si | Si | Si | Si | Si | Si | Si | Si | Si |
| **Declarativo** | Si | No | No | YAML | YAML | No | No | JSON | YAML | YAML | DSL | DSL | DSL |
| **Visualizacion** | No | Si | Eventos | No | Si | No | No | No | Si | Si | Si | Si | Si |
| **Resumability** | Si | Cache | No | No | Cache | No | No | No | Si | Si | Si | Si | Si |
| **Dry run** | No | No | No | Si | Si | No | No | No | Si | Si | No | Si | Si |
| **StepConfig** | Si | No | No | No | No | Parcial | No | No | No | No | No | No | No |
| **Zero deps** | Si | No | Si | No | No | No | No | No | No | No | No | No | No |

---

## Scorecard (0-5)

| Libreria | Encadenado | Declarativo | Visualizacion | Resumability | Dry run | Total |
|----------|------------|-------------|---------------|--------------|---------|-------|
| **Custom wx41** | 5 | 4 | 0 | 5 | 0 | **14** |
| pipefunc | 5 | 0 | 4 | 4 | 0 | 13 |
| justpipe | 5 | 0 | 3 | 0 | 0 | 8 |
| pypyr | 5 | 5 | 0 | 0 | 5 | 15 |
| pipelime | 5 | 5 | 4 | 4 | 5 | **23** |
| pipeco | 4 | 0 | 0 | 0 | 0 | 4 |
| dynapipeline | 5 | 0 | 0 | 0 | 0 | 5 |
| dynaflow | 5 | 4 | 0 | 0 | 0 | 9 |
| dagster | 5 | 5 | 5 | 5 | 5 | **25** |
| prefect | 5 | 5 | 5 | 5 | 5 | **25** |
| nextflow | 5 | 5 | 5 | 5 | 0 | 20 |
| flyte | 5 | 5 | 5 | 5 | 5 | 25 |
| snakemake | 5 | 5 | 5 | 5 | 5 | 25 |

---

## Detalle por Categoria

### Level 1: No recomendadas para wx41

| Libreria | Por qué |
|----------|---------|
| **pipeco** | Muy nueva (0.1.3), API inestable, sin documentation |
| **dynapipeline** | Documentacion incompleta, muy nueva |
| **dynaflow** | Paradigma diferente (ASL), sin resume |
| **justpipe** | Zero deps pero sin declarativo ni resume |
| **nextflow** | Requiere Java, bioinformatic-focused |
| **flyte** | Muy complejo, para ML en escala |
| **snakemake** | Requiere Python 3.9+, workflow-focused |

### Level 2: Parcialmente adecuadas

| Libreria | Pros | Contras |
|----------|------|---------|
| **pipefunc** | DAG auto, visualizacion, map-reduce | Sin declarativo, sin dry-run |
| **pypyr** | YAML declarativo, dry-run, conditional | CLI-oriented, muchas deps |
| **pipelime** | YAML/JSON, dry-run, visualizacion | Data-focused, muchas deps |

### Level 3: Adecuadas pero con tradeoffs

| Libreria | Score | Tradeoff |
|----------|-------|----------|
| **dagster** | 25 | Muy pesado, overkill para wx41 |
| **prefect** | 25 | Muy pesado, overkill para wx41 |
| **pipelime** | 23 | Muchas deps, data-focused |

---

## Conclusion

**Ninguna librería cumple todos los objetivos de wx41 sin tradeoffs significativos.**

### Recomendacion: Implementacion Custom + Patrones

La implementacion custom (wx41 actual) es la unica que:
- Tiene StepConfig propio con output_keys
- Usa PipelineContext con outputs dict
- Es inmutable
- Zero dependencies

**Mejora propuesta:** Agregar a la implementacion custom:
1. **Visualizacion**: Integrar con graphviz o similar
2. **Dry run**: Implementar flag de simulacion
3. **Declarativo**: Usar YAML para configuracion de steps (sin cambiar core)

### Patrones Pythonic Captados

| Patron | Libreria | Aplicacion |
|--------|----------|------------|
| Decoradores | pipefunc, justpipe | Definir steps |
| Clases | pipeco, dynapipeline | Steps con atributos |
| YAML/JSON | pypyr, pipelime, dagster | Configuracion |
| Context/State | justpipe, pypyr | State management |
| Stage/Step | pipelime, dynapipeline | Abstraccion de paso |
