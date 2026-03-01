# TO FIX

## wx41 - Acceptance Test suffixes

El AT actualmente define BACKEND_SUFFIXES como constante local en el test.

**Problema**: Los sufijos deberían leerse desde los wrappers reales (transcribe_whisper.py, transcribe_aai.py) para usar la fuente de verdad.

**Solución**: Importar los sufijos desde los módulos de infraestructura o usar reflexión para obtener los sufijos generados dinámicamente.
