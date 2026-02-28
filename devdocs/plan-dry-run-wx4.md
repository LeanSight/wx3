# Plan: Modo --dry-run para wx4

## Objetivo
Simular la ejecución del pipeline sin realizar cambios, mostrando qué pasos se ejecutarían y cuáles se saltarían (por outputs existentes o configuración).

---

## Estado: COMPLETADO

### Implementación realizada:

1. **Pipeline.dry_run()** - `pipeline.py`
   - Clase `StepDecision` con campos: name, would_run, output_path, reason
   - Método `dry_run()` que itera steps y determina qué se ejecutaría

2. **CLI --dry-run** - `cli.py`
   - Flag `--dry-run` agregado
   - Función `_run_dry_run()` que muestra tabla con decisiones

3. **Unit Tests** - `test_pipeline.py`
   - 5 tests para `TestPipelineDryRun`
   - Todos pasando

---

## Resultados de dry-run en directorio de prueba

```
"Dry Run Mode - Simulating execution without changes"

| File                  | Step        | Would Run | Reason      |
|-----------------------|-------------|-----------|-------------|
| audio1.m4a            | cache_check | Yes       | no_output_fn|
|                       | normalize   | No        | exists      |
|                       | enhance     | No        | exists      |
|                       | cache_save  | Yes       | no_output_fn|
|                       | transcribe  | No        | exists      |
|                       | srt         | No        | exists      |
| video1.mp4           | cache_check | Yes       | no_output_fn|
|                       | normalize   | Yes       | not_exists  |
|                       | enhance     | No        | exists      |
|                       | cache_save  | Yes       | no_output_fn|
|                       | transcribe  | Yes       | not_exists  |
|                       | srt         | Yes       | not_exists  |
|                       | video       | Yes       | not_exists  |
```

---

## Archivos modificados

| Archivo | Cambios |
|---------|---------|
| `wx4/pipeline.py` | +50 líneas: `StepDecision` dataclass, `dry_run()` |
| `wx4/cli.py` | +60 líneas: flag `--dry-run`, `_run_dry_run()` |
| `wx4/tests/test_pipeline.py` | +70 líneas: 5 tests para dry-run |

---

## Uso

```bash
python -m wx4 --dry-run "carpeta_con_archivos"
python -m wx4 --dry-run --video-output "carpeta_con_archivos"
python -m wx4 --dry-run --force "carpeta_con_archivos"
```

---

## Notas

- El dry-run detecta correctamente archivos existentes y muestra "exists" como razón
- Para archivos sin outputs, muestra "not_exists" y Would Run = Yes
- Con `--force`, muestra "force" como razón
- Soporta `--video-output` y `--compress` para mostrar pasos adicionales
