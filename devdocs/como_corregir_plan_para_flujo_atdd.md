# Como corregir el plan para que el agente no viole el flujo ATDD/TDD

Fecha: 2026-02-28
Contexto: plan_wx41.md implementado por Claude Code

---

## El problema de raiz

Un plan que describe QUE construir no es suficiente para un agente LLM.
El agente optimiza para "completar la tarea", y su camino mas corto es
escribir produccion y tests al mismo tiempo en un solo bloque.

El plan actual tiene esta forma:
```
Slice 1 - Walking Skeleton:
  RED   -> escribir AT, falla porque el step no existe
  GREEN -> implementar step + Nullables via monkeypatch
  COMMIT + PUSH
```

Esto DESCRIBE el ciclo correcto pero no lo ENFORZA. El agente lee
"RED -> ... -> GREEN" como descripcion del resultado esperado, no como
una secuencia de pasos con verificaciones intermedias obligatorias.

Resultado: el agente escribe todo junto y pasa directamente a GREEN.

---

## Lo que los expertos recomiendan para planes ejecutados por Claude Code

### 1. Separar el plan en fases con "stop gates" explícitos

Fuente: alexop.dev (2026) — "Forcing Claude Code to TDD"
https://alexop.dev/posts/custom-tdd-workflow-claude-code-vue/

El problema de una sola ventana de contexto: el agente no puede separar
la "mente del test writer" de la "mente del implementer". La solucion
no es pedirle que lo haga — es forzar separacion fisica.

Patron recomendado: cada fase del ciclo TDD debe ser una instruccion
separada con verificacion antes de avanzar. En lugar de:
```
Slice N: RED -> GREEN -> COMMIT
```

Debe ser:
```
FASE A: Escribir solo el test. Ejecutar. Ver RED. Mostrar output.
        -> NO continuar hasta confirmar RED en consola.
FASE B: Escribir produccion minima. Ejecutar. Confirmar GREEN.
FASE C: Commit.
```

### 2. Comandos de verificacion obligatorios en el plan

Fuente: Simon Willison (2026) — Red/Green TDD for Agentic Development
https://simonwillison.net/guides/agentic-engineering-patterns/red-green-tdd/

"It's important to confirm that the tests fail BEFORE implementing the code.
If you skip that step you risk building a test that passes already."

El plan debe incluir el comando pytest con la salida esperada ANTES de
escribir produccion. Si el plan dice "pytest debe fallar aqui", el agente
tiene una verificacion concreta que hacer — no una instruccion abstracta.

### 3. Instrucciones de proceso en CLAUDE.md, no solo en el plan

Fuente: Morph (2026) — Claude Code Best Practices
https://www.morphllm.com/claude-code-best-practices

El CLAUDE.md es leido en cada sesion y anula el comportamiento por defecto.
Las reglas de proceso deben vivir aqui, no solo en el plan de feature.
El plan describe QUE hacer; el CLAUDE.md describe COMO comportarse.

### 4. Checklist de verificacion visible en cada slice

Fuente: TDD Guard — Nizar Selander (2026)
https://nizar.se/tdd-guard-for-claude-code/

TDD Guard enforza TDD via hooks que bloquean escritura de archivos si no
hay test en RED. Sin hooks, el equivalente en un plan es un checklist
que el agente DEBE completar antes de avanzar. El agente respeta
listas de verificacion cuando estan explicitamente en el contexto.

---

## Cambios concretos al plan_wx41.md

### Cambio 1: Reemplazar la descripcion del ciclo por instrucciones de pasos

ANTES (describe el resultado):
```
Slice 1 - Walking Skeleton:
  RED   -> escribir AT, falla porque el step no existe
  DIAG  -> mejorar assert msgs con f-strings
  GREEN -> implementar step + Nullables via monkeypatch
  COMMIT + PUSH
```

DESPUES (prescribe los pasos con verificaciones):
```
Slice 1 - Walking Skeleton:

PASO 1: Escribir SOLO el test (cero produccion).
PASO 2: pytest wx41/tests/ -v -k "<nombre_test>"
        -> Output esperado: FAILED o ERROR (ImportError es valido)
        -> Si pasa GREEN sin produccion: el test esta mal, reescribirlo
PASO 3: Mejorar el mensaje de fallo con f-strings hasta que sea
        autoexplicativo sin debugger.
PASO 4: Escribir produccion minima para pasar ese test.
PASO 5: pytest wx41/tests/ -v -> DEBE ser GREEN
PASO 6: git commit + git push
```

### Cambio 2: Para cada slice del plan, agregar el comando pytest esperado

Cada slice del plan debe incluir:

```
Verificacion RED (ejecutar antes de escribir produccion):
  pytest wx41/tests/test_<step>.py -k "<nombre_test>" 2>&1 | grep -E "PASSED|FAILED|ERROR"
  Resultado esperado: FAILED

Verificacion GREEN (ejecutar despues de escribir produccion):
  pytest wx41/tests/ -v 2>&1 | tail -5
  Resultado esperado: N passed, 0 failed
```

### Cambio 3: Separar AT de unit tests en el plan

El plan mezcla la descripcion del AT con la de los unit tests.
Debe quedar claro que son dos loops distintos:

```
## Slice N — [Nombre]

### Loop externo: Acceptance Test (test_acceptance.py)

Escribir primero. Permanece RED hasta que todos los unit tests esten GREEN.
pytest wx41/tests/test_acceptance.py -> RED

AT:
  def test_<comportamiento_observable>(tmp_path, monkeypatch):
      ...asserts sobre archivos en disco o ctx fields...

### Loop interno: Unit tests (test_<step>.py)

Por cada slice del step, seguir el ciclo nano:
  1. Escribir test -> pytest -> RED
  2. Produccion minima -> pytest -> GREEN

[lista de slices del step]

### Cierre del loop externo

pytest wx41/tests/test_acceptance.py -> GREEN
-> Recien aqui hacer commit
```

### Cambio 4: Agregar seccion "Protocolo de implementacion" al inicio del plan

Antes de cualquier slice, el plan debe tener una seccion que el agente
lea primero y siga estrictamente:

```markdown
## Protocolo de implementacion (LEER ANTES DE CUALQUIER SLICE)

Este plan se implementa con Double Loop TDD (GOOS). El orden es OBLIGATORIO:

1. Loop externo (AT): escribir test_acceptance.py para el slice.
   -> Ejecutar pytest -> confirmar RED en consola
   -> Si pasa GREEN: el test no verifica nada nuevo. Corregir antes de continuar.

2. Loop interno por cada unit test:
   a. Escribir el test en test_<step>.py
   b. Ejecutar pytest -k "<nombre>" -> confirmar RED
   c. Escribir produccion minima
   d. Ejecutar pytest -> confirmar GREEN

3. Verificar que el AT ahora pasa GREEN.

4. Hacer commit atomico. UN slice = UN commit = UN push.

REGLA ABSOLUTA: nunca escribir produccion en el mismo paso que el test.
Si pytest pasa sin produccion: parar, el test esta mal.
```

---

## Cambios a CLAUDE.md

Agregar al archivo CLAUDE.md del proyecto la siguiente seccion.
El CLAUDE.md es leido en cada sesion y tiene precedencia sobre cualquier
instruccion del plan:

```markdown
## Flujo TDD — Comportamiento obligatorio

Al implementar cualquier feature o slice de plan_wx41.md:

NUNCA escribir codigo de produccion y su test en el mismo bloque.
El orden es invariable:

1. Escribir el test
2. Ejecutar: pytest <archivo_test> -k "<nombre>" 2>&1 | tail -10
3. Verificar que la salida muestra FAILED o ERROR
4. Si muestra PASSED: el test esta mal. Parar y corregir el test.
5. Solo entonces escribir produccion minima
6. Ejecutar pytest y verificar GREEN

Los ATs viven en wx41/tests/test_acceptance.py
Los unit tests viven en wx41/tests/test_<step>.py

Un slice = un commit. No agrupar slices en un commit.
```

---

## Por que el plan actual falla aunque describe el ciclo correcto

El agente interpreta el plan de esta forma:

| Lo que dice el plan | Lo que interpreta el agente |
|--------------------|-----------------------------|
| "RED -> escribir AT" | "necesito un test que eventualmente falle" |
| "DIAG -> mejorar msgs" | "los msgs ya tienen f-strings, OK" |
| "GREEN -> implementar" | "implementar junto con el test en un solo paso" |
| "COMMIT + PUSH" | "hacer commit cuando todo este listo" |

El agente no interpreta "->" como "ejecutar pytest y verificar el output
antes de continuar". Lo interpreta como "el resultado final debe tener
esta secuencia logica".

La diferencia clave: el plan actual describe un proceso. El agente necesita
instrucciones con verificaciones ejecutables en cada paso.

---

## Resumen de cambios por archivo

| Archivo | Cambio | Efecto |
|---------|--------|--------|
| `devdocs/plan_wx41.md` | Reemplazar descripcion de ciclo por pasos con comandos pytest | El agente tiene verificaciones concretas que ejecutar |
| `devdocs/plan_wx41.md` | Agregar seccion "Protocolo de implementacion" al inicio | El agente lee las reglas antes de empezar cualquier slice |
| `devdocs/plan_wx41.md` | Separar AT de unit tests en cada slice | El double loop es visible y separado |
| `CLAUDE.md` | Agregar seccion "Flujo TDD" con regla absoluta | Se aplica en cada sesion, no solo cuando el agente lee el plan |

El cambio mas efectivo es CLAUDE.md: si el comportamiento esta ahi,
el agente lo aplica sin que el plan lo repita en cada slice.
