# Arquitectura wx41: Configuración Modular por Composición

Este documento describe el patrón de diseño para la configuración de steps en wx41, diseñado para maximizar la modularidad y el desacoplamiento.

## Principios Core

1. **Step Ownership**: Cada step define su propia estructura de datos (`StepConfig`) para sus parámetros de infraestructura y secretos.
2. **Generic Transport**: `PipelineConfig` transporta una "bolsa" genérica de configuraciones (`settings: Dict[str, Any]`) para evitar hardcodear campos en el núcleo.
3. **Closure Injection**: El `Builder` inyecta la configuración específica al step mediante una clausura o `partial` en el momento de ensamblar el pipeline.
4. **CLI Bundling**: El `cli.py` es el único que mapea argumentos de consola a objetos de configuración específicos de cada step.

## Implementación del Patrón

### 1. En el Step (`wx41/steps/mi_step.py`)
Define un `dataclass` para los parámetros y recíbelo como argumento adicional.

```python
@dataclass(frozen=True)
class MiStepConfig:
    parametro_infra: str = "default"
    secreto_api: Optional[str] = None

@timer("mi_step")
def mi_step(ctx: PipelineContext, config: MiStepConfig) -> PipelineContext:
    # Usa config.secreto_api aquí
    return ctx
```

### 2. En el Builder (`wx41/pipeline.py`)
Extrae la configuración de la bolsa genérica e inyéctala al step.

```python
def build_audio_pipeline(config: PipelineConfig, observers) -> Pipeline:
    # Extraer config específica (o usar default)
    m_cfg = config.settings.get("mi_step", MiStepConfig())
    
    # Inyectar vía lambda en la factoría _step
    step_inst = _step(
        "mi_step",
        lambda ctx: mi_step(ctx, m_cfg),
        "campo_resultado_ctx"
    )
    return Pipeline([step_inst], observers)
```

### 3. En el CLI (`wx41/cli.py`)
Agrupa los argumentos en el objeto de configuración del step.

```python
@app.command()
def main(
    param_cli: str = typer.Option("default", "--param"),
    key_cli: str = typer.Option(None, "--key", envvar="MI_KEY")
):
    settings = {
        "mi_step": MiStepConfig(parametro_infra=param_cli, secreto_api=key_cli)
    }
    config = PipelineConfig(settings=settings)
    orchestrator.run(src, config)
```

## Ventajas para el Agente
- **Escalabilidad**: Añadir un step no requiere modificar `context.py`.
- **Agnosticismo**: El `PipelineContext` (estado) permanece libre de secretos de infraestructura.
- **Localidad**: Todo lo que un step necesita saber sobre sí mismo está en su propio archivo.
