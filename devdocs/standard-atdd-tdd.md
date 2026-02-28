# Metodología: ATDD + TDD + One-Piece-Flow + A-Frame Architecture

---

## Principios

1. **ATDD primero**: el acceptance test describe el comportamiento deseado desde afuera del sistema (como lo ve el usuario o el pipeline completo). Se escribe en RED antes de tocar producción.

2. **TDD hacia adentro**: para implementar lo que el AT exige, se escriben unit tests en RED antes de escribir el código de producción. El orden es siempre: AT rojo → unit test rojo → código mínimo verde.

3. **Red-Green-Refactor-Diagnóstico**: el ciclo tiene 4 pasos, no 3. Después de RED y antes de escribir producción, mejorar el mensaje de fallo del test hasta que describa exactamente qué está mal sin necesidad de debugger. Solo entonces escribir producción para GREEN. El refactor ocurre únicamente cuando todos los tests son GREEN.

4. **One-piece-flow**: el trabajo se divide en slices verticales mínimos. Cada slice atraviesa todas las capas necesarias (test + producción) y termina en GREEN antes de abrir el siguiente.

5. **Commit + push por cada GREEN**: inmediatamente después de que un test (AT o Unit) pase a GREEN, se genera un commit y se pushea. No esperar al final del slice.

---

## PASO 0: Primera decisión antes de escribir código

```
¿Es código nuevo?      → Sección 1 (Walking Skeleton)
¿Es código existente?  → Sección 8 (Legacy)
```

---

## Ciclo por slice

```
1. Identificar el comportamiento del slice (una sola cosa)
2. Escribir AT en test_acceptance → RED
3. Mejorar mensaje de fallo del AT hasta que sea autoexplicativo
4. Escribir unit tests en la capa afectada → RED
5. Mejorar mensajes de fallo de los unit tests
6. Escribir producción mínima → GREEN
7. **git commit + git push (INMEDIATO)**
8. Refactor si es necesario (tests siguen GREEN)
9. **git commit + git push (si hubo cambios)**
10. Avanzar al siguiente slice
```

**Reglas:**
- **Un GREEN = un commit = un push**
- Nunca avanzar al slice N+1 si el slice N no está en GREEN
- **NUNCA** cambiar el orden de implementación de los slices presentado en un plan

---

## PASO 1: Walking Skeleton (solo en proyectos nuevos)

Antes de cualquier feature, crear el esqueleto mínimo que cruce todas las capas.

1. Crear pipeline de deployment funcional
2. Implementar el flujo más simple end-to-end (entrada → proceso → salida)
3. Hardcodear los datos, sin lógica real
4. Cubrir con un Smoke Test que pase

No continuar hasta que este Smoke Test sea verde.

---

## PASO 2: Estructura de directorios (mantener siempre)

```
src/
├── logic/           # Funciones puras. Cero I/O.
├── infrastructure/  # Wrappers de sistemas externos.
├── application/     # Coordina logic e infrastructure.
└── app.ts           # Entry point.
```

---

## PASO 3: Regla estructural — nunca violar

```
logic/          NO puede importar nada de infrastructure/
infrastructure/ NO puede importar nada de logic/
application/    ES el único que importa de ambos
```

Si una función en `logic/` necesita leer de la DB → está mal ubicada.
Si una función en `infrastructure/` tiene un `if` de negocio → está mal ubicada.

No crear interfaces con exactamente una clase implementándola. Una interfaz solo existe cuando hay múltiples implementaciones reales posibles.

---

## PASO 4: Ciclo por cada feature

### 4.1 Escribir AT (quedará rojo)

El AT ejerce el camino completo desde la entrada del sistema (CLI, API, evento) hasta el efecto observable (archivo generado, estado del contexto, respuesta). Cubre el "wiring" entre capas: si dos capas se conectan mal, el AT lo detecta aunque los unit tests de cada capa estén en GREEN.

```python
# test_acceptance.py
def test_comportamiento_completo():
    resultado = app.run(inputs)
    assert resultado == output_esperado
```

Mejorar el mensaje de fallo antes de continuar:
```python
assert resultado == output_esperado, (
    f"Se esperaba {output_esperado!r} pero se obtuvo {resultado!r}"
)
```

### 4.2 Clasificar cada operación del feature

Antes de escribir código, clasificar cada operación:

| ¿Qué hace? | Tipo | Va en |
|---|---|---|
| Lee DB, HTTP, filesystem, stdin | Infrastructure.read | `infrastructure/` |
| Transforma datos, aplica reglas de negocio | Logic.transform | `logic/` |
| Escribe DB, HTTP, UI, stdout | Infrastructure.write | `infrastructure/` |
| Coordina los tres | Application | `application/` |

### 4.3 Implementar Logic primero

```python
# logic/nombre_dominio.py
# Solo recibe datos, solo retorna datos. Sin imports de I/O.

def procesar_evento(estado, evento, parametros):
    # lógica pura aquí
    return {"nuevo_estado": ..., "comando": ...}
```

Unit test inmediato, sin setup:

```python
# test_logic.py
def test_descripcion_del_comportamiento():
    resultado = procesar_evento(estado_inicial, evento, parametros)

    assert resultado["nuevo_estado"] == "ESPERADO", (
        f"Estado incorrecto: {resultado['nuevo_estado']!r}"
    )
    assert resultado["comando"] == comando_esperado, (
        f"Comando incorrecto: {resultado['comando']!r}"
    )
```

### 4.4 Implementar Infrastructure Wrappers

Cada wrapper de sistema externo tiene dos factories:

```python
# infrastructure/nombre_wrapper.py

class MiWrapper:
    @classmethod
    def create(cls, cliente_real):
        return cls(cliente_real)

    @classmethod
    def create_null(cls, datos_simulados=None):
        # Sin I/O real — para tests de capas superiores
        return cls(ClienteSimulado(datos_simulados or {}))

    def track_output(self):
        # Para verificar qué escribió el wrapper en tests
        return OutputTracker(self)
```

Test del wrapper con sistema externo real (de test, no producción):

```python
# test_infrastructure.py
def test_lee_dato_correctamente():
    wrapper = MiWrapper.create(cliente_de_test)
    resultado = wrapper.leer("id-123")
    assert resultado == dato_esperado
```

### 4.5 Implementar Application layer

Patrón fijo: **read → transform → write**. Sin lógica de negocio aquí.

```python
# application/nombre_feature.py

def ejecutar_feature(input_data, deps):
    # 1. Leer del mundo externo
    datos = deps.repositorio.leer(input_data["id"])

    # 2. Transformar con Logic pura
    resultado = procesar_evento(datos["estado"], input_data["evento"], datos["parametros"])

    # 3. Escribir si hay comando
    if resultado["comando"] != Comando.ninguno():
        deps.servicio.enviar(resultado["comando"])

    return resultado["nuevo_estado"]
```

Test del Application layer usando Nullables — sin mocks, ejecuta Logic real:

```python
# test_application.py
def test_envia_comando_cuando_corresponde():
    repositorio = Repositorio.create_null({"id-1": datos_de_test})
    servicio = Servicio.create_null()
    mensajes_enviados = servicio.track_output()

    ejecutar_feature({"id": "id-1", "evento": evento_de_test}, deps={
        "repositorio": repositorio,
        "servicio": servicio,
    })

    assert comando_esperado in mensajes_enviados.data, (
        f"Comando no enviado. Enviados: {mensajes_enviados.data!r}"
    )
```

### 4.6 AT verde = feature completa

Si el AT sigue rojo, hay un gap de wiring. Agregar unit tests específicos para la frontera que falla, no ampliar el AT.

---

## PASO 5: Decisión rápida para cada línea de código

```
¿Necesita I/O (DB, HTTP, filesystem, UI)?
  └── NO → va en logic/ como función pura
  └── SÍ → ¿tiene también reglas de negocio?
              └── NO → va en infrastructure/ como wrapper
              └── SÍ → SEPARAR:
                        regla  → logic/
                        I/O    → infrastructure/
                        coord  → application/
```

---

## PASO 6: Tests — técnica según tipo de clase

| Tipo de clase | Técnica | Usa mocks |
|---|---|---|
| `logic/` | State-Based: input directo → assert output | Nunca |
| `infrastructure/` | Narrow Integration Test con sistema real de test | Nunca |
| `application/` | Sociable Test con Nullables de infrastructure | Nunca |

**Nunca verificar orden de llamadas entre métodos.** Verificar siempre el output o el estado resultante.

---

## PASO 7: Tests existentes y cambios de comportamiento

Los tests de slices anteriores no deben regresar a RED. Si un cambio rompe un test existente:

**a) El comportamiento cambió intencionalmente** → corregir el test en el mismo slice para reflejar el nuevo comportamiento. El test pasa a RED y se corrige siguiendo TDD.

**b) El comportamiento no debería cambiar** → diagnosticar y corregir el código de producción. El test está correcto; detecta RED y debe volver a GREEN.

Esta regla aplica a cualquier cambio de comportamiento.

---

## PASO 8: Código existente (Legacy)

Subir la cadena de dependencias de adentro hacia afuera:

1. Identificar la clase más alejada de I/O en la cadena
2. Escribir un test que documente su comportamiento actual
3. Extraer su lógica pura a `logic/`
4. Testear la función extraída con State-Based Test
5. Reemplazar la lógica original con llamada a la función nueva
6. Repetir con la clase siguiente en la cadena hacia Application

Un comportamiento a la vez. Mantener tests verdes en cada paso.

---

## PASO 9: Señales de stop — corregir antes de continuar

Detener si aparece cualquiera de estas condiciones:

- `logic/` importa repositorio, cliente HTTP, o cualquier servicio externo
- `infrastructure/` contiene condicionales de negocio
- Existe una interfaz con exactamente una clase implementándola
- Dos clases se importan mutuamente (dependencia cíclica)
- Un test verifica orden de llamadas entre métodos
- Una función de `logic/` retorna `void` y modifica estado externo
- `application/` contiene reglas de negocio (no es solo orquestación)
- Se avanza al siguiente slice con tests en RED
