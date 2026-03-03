# Brechas: wx41.md vs plan_wx41.md vs Implementacion

Fecha: 2026-03-02
Estado: 1 PENDIENTE

---

## BRECHA 8 — Meta-AT: cobertura incompleta

**Donde**: `wx41/tests/test_acceptance.py`
**Doc dice** (`meta_at_design.md`): El Meta-AT debe cubrir "tests sin fixture real y test con fixture real"
**Doc dice** (`endtoendtests.md`): AT en `test_acceptance.py` debe cover "todo el wiring entre capas"
**Realidad**: Solo existe 1 test con fixture real (`TestPipelineWalkingSkeleton`), no esta parametrizado ni cubre todos los steps.

**Impacto**: Meta-AT incompleto. Falta coverage de integration con fixture real para todos los steps.

### Diseño (propuesta)

```python
class TestMetaATWithRealFixture:
    @pytest.mark.parametrize("step_name", get_all_steps().keys())
    def test_step_produces_real_outputs(self, step_name, audio_file, tmp_path):
        step_info = get_step_info(step_name)
        if not step_info.config_class:
            pytest.skip(f"{step_name} no tiene config_class")
        
        cfg = step_info.config_class()
        
        ctx = PipelineContext(
            src=audio_file,
            media_type="audio",
            force=False,
            dry_run=False,
            outputs={}
        )
        
        result = step_info.step_fn(ctx, cfg)
        
        for key in cfg.output_keys:
            assert key in result.outputs, f"{step_name}: {key} not in outputs"
            assert result.outputs[key].exists(), f"{step_name}: {key} file not created"
```

**Principio**: Same parametrize structure as mock tests, but using `audio_file` fixture.

---

## Resumen por prioridad

| # | Brecha | Estado | Donde corregir | Tipo | Impacto |
|---|--------|--------|----------------|------|---------|
| 1 | JSON state vs file-based Ctrl+C | ✅ RESUELTA | `wx41.md` + codigo | Contradiccion + refactor | **Critico** |
| 4 | "Mejor Audio" sin fallback a src | ✅ RESUELTA | `wx41.md` + codigo | Completado | **Alto** |
| 5 | update_ctx letra muerta | ✅ RESUELTA (via BRECHA 1) | - | Bug | **Alto** |
| 2 | pipeline.py → pipeline_engine.py | ✅ RESUELTA | `plan_wx41.md` | Nombre incorrecto | Medio |
| 3 | metadata-driven → disk-based | ✅ RESUELTA | `plan_wx41.md` | Descripcion incorrecta | Medio |
| 6 | Modulos no documentados | ✅ RESUELTA | `wx41.md` | Completado | Bajo |
| 7 | MediaType clase vs Enum | ✅ RESUELTA | `wx41.md` | Completado | Bajo |
| 8 | Meta-AT coverage incompleto | PENDIENTE | `test_acceptance.py` | Incompleto | **Alto** |
