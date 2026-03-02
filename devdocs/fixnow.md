# Fix Now: Brechas de Arquitectura y Modularidad en wx41

Este documento detalla las brechas críticas detectadas entre la implementación actual de `wx41` y los principios definidos en `devdocs/arquitectura.md` y `devdocs/plan_wx41.md`.

## 1. Brecha de Modularidad: Acoplamiento de Imports (RESUELTA)

*   **Acción Correctiva**: Implementado auto-descubrimiento de steps en `wx41/steps/__init__.py` usando `pkgutil`. `pipeline.py` y `cli.py` ya no importan steps específicos.

## 2. Brecha de Agnosticismo: Lógica Hardcoded en CLI (RESUELTA)

*   **Acción Correctiva**: `cli.py` ahora utiliza `get_all_steps()` y `dataclasses.fields()` para configurar steps de forma genérica. Se eliminaron los bloques `if name == "transcribe"`.

## 3. Brecha de Escalabilidad: Firma de CLI Estática (RESUELTA)

*   **Acción Correctiva**: La CLI ahora genera opciones dinámicamente (`--{step}-{field}`) basándose en el registro de steps y sus `StepConfig`.

## 4. Observaciones "Pythonic" (Mejora de Código) (RESUELTA)

*   **Clausuras vs Partial**: Migrado a `functools.partial` en `pipeline.py`.
*   **Fuente de Verdad**: Los tests ya no hardcodean keys de output, usan la metadata del config/registro.
*   **Contratos de Configuración**: Definido `StepConfig(Protocol)` en `context.py` para garantizar campos comunes (`enabled`, `output_keys`). El pipeline ahora valida las configuraciones contra este protocolo.

