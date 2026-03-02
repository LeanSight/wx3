# Diseño: Meta-AT Registry-Driven (Smoke Test 2026)

Este documento describe el diseño del Test de Aceptación Universal para `wx41`, diseñado para crecer automáticamente con el pipeline sin mantenimiento manual.

## 1. El Concepto: "El Oráculo del Registro"

En lugar de escribir un test por cada step, el sistema de tests se convierte en un **consumidor del `STEP_REGISTRY`**. El test utiliza la metadata declarada por cada step para configurar sus expectativas y aserciones.

## 2. Componentes Arquitectónicos

### A. Parametrización Dinámica
Utiliza la fase de recolección de `pytest` para generar un caso de test por cada step registrado.
- **Beneficio**: Aislamiento total. Si `normalize` falla, no detiene la prueba de `transcribe`. Reportes claros en CI.

### B. Simulador de Infraestructura Universal
Un componente que intercepta las llamadas a las funciones de lógica de los steps (`step_fn`) y simula su éxito.
- **Mecánica**: 
    1. Lee los `output_keys` desde el `StepConfig`.
    2. Utiliza el "Oráculo de Rutas" para saber dónde deberían estar esos archivos.
    3. Crea archivos vacíos (`touch`) en esas ubicaciones.
    4. Registra la llamada para validar resumability.

### C. Oráculo de Rutas (Pure Function)
Una función compartida entre producción y tests que encapsula la convención de nombres de archivos.
```python
def get_predictable_path(src: Path, step_name: str, key: str) -> Path:
    # Lógica centralizada de nombres (ej: src_normalized.m4a)
```

## 3. Flujo del Meta-AT

1.  **Discovery**: El test carga todos los módulos de `wx41.steps`.
2.  **Mocking**: Se aplica un "Massive Monkeypatch" a todas las `step_fn` del registro.
3.  **Execution**: Se invoca el CLI (`click.testing.CliRunner`).
4.  **Verification**:
    - **Existencia**: Se verifica que cada archivo declarado en `output_keys` existe.
    - **Optionality**: Se verifica que si se pasa `--no-{step}`, el simulador NO fue llamado y los archivos NO existen.
    - **Resumability**: Se ejecuta una segunda vez y se verifica que el contador de llamadas al simulador es 0.

## 4. Estructura del Test en `test_acceptance.py`

```python
@pytest.mark.parametrize("step_name", get_all_steps().keys())
class TestStepContract:
    def test_cli_lifecycle(self, step_name, tmp_path, runner):
        # 1. Configuración del Oráculo y Simulador
        # 2. Ejecución CLI
        # 3. Aserción de Archivos y Estado
```

## 5. Ventajas para el Desarrollo (DX)

- **Cero mantenimiento**: Al agregar `srt.py` y llamar a `register_step`, el test de aceptación ya existe y está pasando (o fallando si la metadata es inconsistente).
- **Validación de Contratos**: Obliga a que todos los steps cumplan con el `StepConfig` protocol.
- **Velocidad**: Al simular la infraestructura, el AT completo de todo el pipeline corre en milisegundos.
