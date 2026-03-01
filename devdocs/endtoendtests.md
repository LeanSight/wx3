# End-to-End Tests (AT)

## Ubicacion

- AT: `wx41/tests/test_acceptance.py` (loop externo)
- Unit tests: `wx41/tests/test_<step>.py` (loop interno)

## Reglas

1. **AT primero**: Escribir el AT antes de cualquier produccion. Debe fallar.
2. **Seguir arquitectura.md**: Cada step debe definir su `StepConfig` con `output_keys`. El AT debe usar esas keys, nunca hardcodear nombres.
3. **Outputs del config**: Usar `config.output_keys` del StepConfig, no valores hardcodeados.
4. **Verificar comportamiento observable**: Archivos en disco, campos en ctx, respuestas.
5. **Un AT por feature/slice**: Cover todo el wiring entre capas.
6. **AT verde = feature completa**: No avanzar al siguiente slice si el AT esta en rojo.

## Ejemplo

```python
def test_produces_transcript_files(self, audio_file):
    config = PipelineConfig(
        settings={"transcribe": TranscribeConfig(backend="whisper")}
    )
    transcribe_cfg = config.settings["transcribe"]
    
    ctx = MediaOrchestrator(config, []).run(audio_file)

    for key in transcribe_cfg.output_keys:
        assert key in ctx.outputs, f"{key} not in outputs"
        assert ctx.outputs[key].exists(), f"Output file not found: {key}"
```

## No hacer

- No hardcodear sufijos de archivo en el AT
- No mezclar AT con unit tests en el mismo archivo
- No escribir produccion y test en el mismo paso
