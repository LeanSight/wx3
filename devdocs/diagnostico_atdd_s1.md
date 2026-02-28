# Diagnostico: Violaciones ATDD/TDD en S1 y Correcciones Recomendadas

Fecha: 2026-02-28
Contexto: Implementacion de wx41/S1 (Walking Skeleton)

---

## 1. Que paso — Descripcion de las violaciones

### V1 (GRAVE) — Produccion y tests escritos al mismo tiempo

El flujo correcto del standard (devdocs/standard-atdd-tdd.md) exige:

```
AT RED  ->  mejorar mensaje  ->  unit test RED  ->  mejorar mensaje  ->  produccion  ->  GREEN
```

Lo que ocurrio en S1:

```
[produccion + tests escritos en el mismo bloque]  ->  pytest  ->  fix puntual  ->  GREEN
```

En un solo mensaje se crearon 13 archivos simultaneamente:
context.py, step_common.py, transcribe_aai.py, transcribe_wx3.py,
steps/transcribe.py, pipeline.py, cli.py, tests/conftest.py,
tests/test_transcribe_step.py, y cuatro __init__.py.

Nunca existio un momento en que el AT estuviera en RED con produccion
ausente. El ciclo DIAG (mejorar mensajes de fallo) fue completamente omitido.

### V2 — AT mezclado con unit tests en el mismo archivo

El AT real del pipeline (TestPipelineWalkingSkeleton) vive en
wx41/tests/test_transcribe_step.py junto a los unit tests de transcribe_step.

El standard exige separacion fisica:
- Loop externo (AT): test_acceptance.py
- Loop interno (unit tests): test_<step>.py

Sin esta separacion no es posible ejecutar el outer loop en aislamiento
para confirmar que el wiring entre capas esta roto antes de que los
unit tests pasen.

### V3 — Assertion .exists() vacia en test_assemblyai_happy_path

```python
# Como estaba:
txt, jsn = _fake_files(tmp_path, "audio")  # crea archivos en disco
result = transcribe_step(ctx)
assert result.transcript_txt.exists()      # SIEMPRE True: archivo preexistia
```

`_fake_files` crea `audio_transcript.txt` y `audio_timestamps.json` en disco
ANTES de llamar a `transcribe_step`. La assertion `.exists()` pasa aunque
el step no haga nada, porque los archivos ya existen desde el fixture.

El test no detectaria una regresion donde el step dejara de crear los archivos.
El Nullable debe ser quien cree los archivos, no el helper de setup.

### V4 — force derivado de compress_ratio en MediaOrchestrator

```python
# Como estaba en pipeline.py:
ctx = PipelineContext(
    src=src,
    force=self._config.compress_ratio is not None,  # logica de negocio incorrecta
    compress_ratio=self._config.compress_ratio,
)
```

`force` es un flag independiente que el usuario activa con `--force`.
No tiene relacion semantica con `compress_ratio`. El campo `force` debe
vivir en `PipelineConfig` y pasarse directamente.

### V5 (LATENTE) — ctx_setter de _TRANSCRIBE restaura solo transcript_json

```python
_TRANSCRIBE = _step("transcribe", transcribe_step, "transcript_json")
```

La factory `_step` genera un `ctx_setter` que solo restaura un campo:
```python
ctx_setter=lambda ctx, p: dataclasses.replace(ctx, transcript_json=p)
```

Cuando Pipeline.run() salta el step (archivo ya existe en resume),
restaura `transcript_json` pero NO `transcript_txt`. Este bug no se
manifiesta en S1 porque el step siempre corre. Se manifestara en S5
(Resumability) cuando el pipeline intente saltar transcribe en un re-run.

---

## 2. Que dicen los expertos sobre estas violaciones

### GOOS: Double Loop TDD (Freeman & Pryce)
Fuente: https://growing-object-oriented-software.com/

El patron canonico es dos loops anidados:

```
[AT RED] -----------------> [AT GREEN] -> commit
    |                           ^
    v                           |
  [unit test RED] -> [codigo] -> [unit test GREEN]
  [unit test RED] -> [codigo] -> [unit test GREEN]
  ...
```

El AT permanece RED durante TODO el desarrollo. Solo pasa a GREEN cuando
la feature esta completa y el wiring entre capas funciona end-to-end.
Escribir produccion y test juntos elimina el outer loop completamente.

### Uncle Bob: Las tres leyes de TDD
Fuente: https://blog.cleancoder.com/uncle-bob/2014/12/17/TheCyclesOfTDD.html

Las tres leyes violadas en S1:

1. No escribir codigo de produccion hasta tener un unit test que falle.
2. No escribir mas de un unit test del que sea suficiente para fallar.
3. No escribir mas codigo de produccion del que sea suficiente para pasar.

El ciclo correcto opera en tres escalas de tiempo:
- Nano (segundos): 1 test que falla -> 1 linea de prod -> pasa
- Micro (minutos): grupo de ciclos nano = 1 unit test completo
- Meso (horas): grupo de ciclos micro = 1 AT completo

### Simon Willison: Red/Green para agentes de codigo (2026)
Fuente: https://simonwillison.net/guides/agentic-engineering-patterns/red-green-tdd/

"It's important to confirm that the tests fail BEFORE implementing the code
to make them pass. If you skip that step you risk building a test that passes
already, hence failing to exercise your new implementation."

Para un agente de codigo, el riesgo especifico es:
- El agente escribe test + produccion en el mismo turno
- pytest pasa en el primer run
- Nadie confirmo que el test alguna vez estuvo en RED
- El test puede estar probando el fixture, no el codigo

### TDD Guard (Nizar Selander, 2026)
Fuente: https://nizar.se/tdd-guard-for-claude-code/
Repo: https://github.com/nizos/tdd-guard

Herramienta de hooks para Claude Code que intercepta operaciones de
escritura de archivos ANTES de ejecutarlas. Valida tres violaciones:

1. Implementar funcionalidad sin un test en RED correspondiente
2. Over-implementar mas de lo necesario para pasar el test actual
3. Agregar multiples tests simultaneamente en lugar de uno a la vez

Cuando detecta una violacion, bloquea la accion y devuelve feedback
con guia correctiva. Usa `PreToolUse` hooks que interceptan
Write/Edit/MultiEdit antes de que el agente los ejecute.

### alexop.dev: Arquitectura multi-agente para TDD estricto (2026)
Fuente: https://alexop.dev/posts/custom-tdd-workflow-claude-code-vue/

El problema de fondo: en una sola ventana de contexto, el agente no puede
seguir TDD real. El conocimiento de la implementacion "contamina" la
escritura del test, y viceversa. La solucion es separar fases en subagentes:

- tdd-test-writer: escribe solo el test, sin ver el codigo de produccion
- tdd-implementer: escribe solo produccion para pasar tests en RED
- tdd-refactorer: mejora estructura sin cambiar comportamiento

Un hook `UserPromptSubmit` inyecta logica de evaluacion antes de cada
respuesta, forzando al agente a declarar en que fase esta antes de actuar.
Esto sube la activacion del workflow TDD del 20% al 84%.

---

## 3. Correcciones concretas para este proyecto

### Fix V3 — test_assemblyai_happy_path

```python
# Correcto: el Nullable crea los archivos, no el fixture
def test_assemblyai_happy_path(self, tmp_path, monkeypatch):
    ctx = make_ctx(tmp_path)
    txt = tmp_path / "audio_transcript.txt"
    jsn = tmp_path / "audio_timestamps.json"

    def fake_transcribe(*a, **kw):
        txt.write_text("hello", encoding="utf-8")
        jsn.write_text("[]", encoding="utf-8")
        return txt, jsn

    monkeypatch.setattr("wx41.steps.transcribe.transcribe_assemblyai", fake_transcribe)
    result = transcribe_step(ctx)

    assert result.transcript_txt == txt, f"transcript_txt: {result.transcript_txt}"
    assert result.transcript_txt.exists(), f"archivo no creado: {result.transcript_txt}"
    assert result.transcript_json == jsn, f"transcript_json: {result.transcript_json}"
    assert result.transcript_json.exists(), f"archivo no creado: {result.transcript_json}"
```

### Fix V4 — PipelineConfig.force

```python
# context.py
@dataclass(frozen=True)
class PipelineConfig:
    skip_enhance: bool = False
    skip_normalize: bool = False
    compress_ratio: Optional[float] = None
    force: bool = False                      # AGREGAR

# pipeline.py - MediaOrchestrator.run()
ctx = PipelineContext(
    src=src,
    force=self._config.force,               # CORREGIR
    compress_ratio=self._config.compress_ratio,
)
```

### Fix V2 — Separar AT a test_acceptance.py

Mover TestPipelineWalkingSkeleton de test_transcribe_step.py a un nuevo
archivo wx41/tests/test_acceptance.py.

### Fix V5 — ctx_setter de _TRANSCRIBE (pendiente para S5)

Transcribe retorna dos campos (transcript_txt y transcript_json).
El _step factory no soporta ctx_setters multi-campo. Opciones:
- Usar output_fn=None en _TRANSCRIBE (step siempre corre, no se puede saltar)
- O implementar un ctx_setter custom que restaure ambos campos

---

## 4. Flujo correcto para S2 en adelante

El flujo que debe seguirse en cada slice futuro, sin excepcion:

```
PASO 1 — Escribir AT (sin tocar produccion)
  pytest wx41/tests/test_acceptance.py
  -> DEBE fallar con ImportError o AssertionError
  -> Si pasa: el AT no verifica nada nuevo, reescribirlo

PASO 2 — Mejorar mensaje de fallo del AT
  El mensaje debe decir exactamente que falta, sin debugger

PASO 3 — Escribir un unit test (sin tocar produccion)
  pytest wx41/tests/test_<step>.py -k "<nombre>"
  -> DEBE fallar
  -> Mejorar mensaje de fallo

PASO 4 — Produccion minima para pasar ese unit test
  pytest -> unit test GREEN, AT sigue RED

PASO 5 — Repetir pasos 3-4 para cada unit test del slice

PASO 6 — AT debe pasar GREEN al final
  pytest wx41/tests/ -> TODO GREEN

PASO 7 — Refactor (tests siguen GREEN)

PASO 8 — Commit + push
```

Verificacion obligatoria antes de escribir produccion:
- pytest fue ejecutado y mostro RED en consola
- El mensaje de fallo es autoexplicativo
- Solo entonces se escribe produccion

---

## 5. Ajustes para Claude Code (CLAUDE.md)

Para que el agente siga este flujo automaticamente, agregar a CLAUDE.md:

```markdown
## Flujo TDD obligatorio

Para cada nuevo test o feature:
1. Escribir el test primero
2. Ejecutar pytest y confirmar que falla (RED)
3. Solo si esta en RED: escribir produccion minima
4. Ejecutar pytest y confirmar GREEN
5. Nunca escribir produccion y test en el mismo paso

Si pytest pasa sin haber escrito produccion: el test esta mal,
no verifica el codigo nuevo. Corregir el test antes de continuar.

Los ATs viven en wx41/tests/test_acceptance.py (loop externo).
Los unit tests viven en wx41/tests/test_<step>.py (loop interno).
```

---

## 6. Resumen: que esta bien vs que corregir

| Aspecto | Estado | Accion |
|---------|--------|--------|
| State-Based assertions (no assert_called_with) | OK | mantener |
| Mensajes f-string en assertions | OK | mantener |
| Lazy imports de assemblyai y wx3 | OK | mantener |
| One-piece-flow: S1 termino GREEN | OK | mantener |
| Commit atomico con descripcion | OK | mantener |
| Nullables via monkeypatch | OK (pragmatico) | mantener |
| Ciclo RED -> DIAG -> GREEN | VIOLADO | corregir proceso |
| AT separado en test_acceptance.py | AUSENTE | crear archivo |
| Assertion .exists() en happy path | VACIA | fix en test |
| PipelineConfig.force | AUSENTE | agregar campo |
| ctx_setter de _TRANSCRIBE (multi-campo) | BUG LATENTE | fix antes de S5 |
