# TO FIX

## wx41 - Acceptance Test debe usar outputs registrados

**Problema**: El AT actualmente:
1. Define BACKEND_SUFFIXES como constante local
2. Verifica sufijos hardcodeados

**Arquitectura correcta**:
1. TranscribeConfig debe tener output_keys: tuple[str, str]
2. El step usa esas keys al registrar en ctx.outputs
3. El AT verifica ctx.outputs contiene las keys registradas en config

**Cambios necesarios**:
1. Agregar output_keys a TranscribeConfig
2. Modificar transcribe_step para usar las keys del config
3. AT lee config.output_keys y verifica en ctx.outputs
