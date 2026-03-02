# Arquitectura wx41: Configuración Modular por Composición

Este documento describe el patrón de diseño para la configuración de steps en wx41, diseñado para maximizar la modularidad y el desacoplamiento.

## Principios Core

1. **Step Ownership**: Cada step define su propia estructura de datos (`StepConfig`) para sus parámetros de infraestructura y secretos.
2. **Generic Transport**: `PipelineConfig` transporta una "bolsa" genérica de configuraciones (`settings: Dict[str, Any]`) para evitar hardcodear campos en el núcleo.
3. **Partial Injection**: El `Builder` inyecta la configuración específica al step mediante `functools.partial` en el momento de ensamblar el pipeline.
4. **Registry-Driven Metadata**: Un registro centralizado (`StepInfo`) es la fuente de verdad para la lógica, configuración y opcionalidad de cada step.
5. **Protocol-Based Contracts**: Todos los `StepConfig` deben cumplir con el protocolo `StepConfig` (`enabled`, `output_keys`).

## El Contrato: StepConfig Protocol

En `wx41/context.py`, se define el contrato mínimo que toda configuración de step debe cumplir:

```python
@runtime_checkable
class StepConfig(Protocol):
    enabled: bool
    output_keys: Tuple[str, ...]
```

## Implementación del Patrón

### 1. En el Step (`wx41/steps/mi_step.py`)
Define un `dataclass` que cumpla el protocolo y regístralo.

```python
@dataclass(frozen=True)
class MiStepConfig:
    parametro: str = "default"
    enabled: bool = True
    output_keys: tuple = ("mi_resultado",)

def mi_step(ctx: PipelineContext, config: MiStepConfig) -> PipelineContext:
    # Lógica usando config.parametro
    return ctx

register_step("mi_step", mi_step, mi_output_fn, config_class=MiStepConfig)
```

### 2. En el Builder (`wx41/pipeline.py`)
Extrae la configuración e inyéctala usando `partial`.

```python
def build_audio_pipeline(config: PipelineConfig, observers) -> Pipeline:
    for step_name, step_config in config.settings.items():
        step_info = STEP_REGISTRY.get(step_name)
        if step_info:
            # Inyección limpia vía partial
            step_fn = partial(step_info.step_fn, config=step_config)
            steps.append(NamedStep(name=step_name, fn=step_fn))
```

### 3. En el CLI (`wx41/cli.py`)
El CLI genera opciones dinámicamente inspeccionando los campos de las `StepConfig` registradas.

```python
# Genera automáticamente flags como:
# --mi-step-parametro "valor"
# --no-mi-step (si es opcional)
```

## Fuente de Verdad: Path Oracle

Para evitar desincronización entre steps y tests, la lógica de rutas de salida se centraliza en `wx41/steps/__init__.py`:

```python
def predict_output_path(src: Path, step_name: str, key: str) -> Path:
    # Centraliza la convención de nombres (ej: audio_normalized.m4a)
    ...
```

## Ventajas
- **Escalabilidad**: Añadir un step no requiere modificar el núcleo ni el CLI.
- **Agnosticismo**: El pipeline no conoce los detalles internos de los steps.
- **Testabilidad**: Los tests de aceptación son dinámicos y se guían por el registro de metadata.
