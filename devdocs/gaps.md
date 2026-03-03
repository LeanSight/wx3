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

### Objetivo: Cobertura completa de plan_wx41.md en ambos modelos

| Objetivo (plan_wx41.md) | Meta-AT (Mocks) | Meta-AT (Fixture Real) |
|--------------------------|-----------------|------------------------|
| Encadenado de steps | `TestStepContract::test_step_cli_resumability` | `test_step_produces_real_outputs` |
| Configuracion declarativa dinamica | `TestCLIOptionality::test_cli_configures_step_via_dynamic_flags` | `test_cli_config_flags_propagate` |
| Visualizacion UI | `test_ui_shows_step_name` (unit) | `test_cli_output_contains_step_names` |
| Resumability (disk-based) | `TestStepContract::test_step_cli_resumability` | `test_step_produces_real_outputs` (verifica archivos) |
| Dry run | `TestStepContract::test_step_cli_dry_run` | `test_cli_dry_run_no_files_created` |
| Ctrl+C cleanup | (unit test en `pipeline_engine.py`) | - |
| CLI Agnóstico | `TestCLIOptionality::test_cli_help_shows_dynamic_options` | `test_cli_flags_work_for_step` |
| StepInfo Registry unificado | `TestStepOptionality::test_steps_registry_has_optional_field` | (implicitamente validado) |
| Meta-AT Registry-Driven | `TestStepContract` (existente) | `TestMetaATWithRealFixture` (nuevo) |

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

### 2. Test de CLI con argumentos dinamicos

```python
class TestMetaATCLI:
    @pytest.mark.parametrize("step_name", get_all_steps().keys())
    def test_cli_disable_flag_works(self, step_name, tmp_path, monkeypatch):
        from click.testing import CliRunner
        from wx41.cli import main
        
        step_info = get_step_info(step_name)
        if not step_info.optional:
            pytest.skip(f"{step_name} no es opcional")
        
        audio = tmp_path / "audio.m4a"
        audio.touch()
        
        runner = CliRunner()
        result = runner.invoke(main, [str(audio), f"--no-{step_name}"])
        
        assert result.exit_code == 0, f"CLI falló: {result.output}"
        
        cfg = step_info.config_class()
        for key in cfg.output_keys:
            expected = predict_output_path(audio, step_name, key)
            assert not expected.exists(), f"{step_name} deberia estar deshabilitado"
    
    @pytest.mark.parametrize("step_name,field_name", [
        (name, f.name) 
        for name in get_all_steps().keys() 
        if (info := get_step_info(name)) and info.config_class
        for f in fields(info.config_class) 
        if f.name not in ("enabled", "output_keys")
    ])
    def test_cli_config_flags_propagate(self, step_name, field_name, tmp_path, monkeypatch):
        from click.testing import CliRunner
        from wx41.cli import main
        from wx41.wx4 import MediaOrchestrator
        
        captured = []
        def capture_run(self, src, **kwargs):
            captured.append(self._config.settings.get(step_name))
            from wx41.context import PipelineContext
            return PipelineContext(src=src)
        
        monkeypatch.setattr(MediaOrchestrator, "run", capture_run)
        
        audio = tmp_path / "audio.m4a"
        audio.touch()
        
        runner = CliRunner()
        runner.invoke(main, [str(audio), f"--{step_name}-{field_name}", "test_value"])
        
        assert len(captured) == 1
        cfg = captured[0]
        assert getattr(cfg, field_name, None) == "test_value"
```

---

## Plan Incremental (ATDD/TDD)

### Slice 1: Meta-AT con Fixture Real - test_step_produces_real_outputs

**Comportamiento**: Cada step debe producir outputs reales en disco cuando se ejecuta con fixture de audio real.

**Ciclo**:
1. Escribir AT en `test_acceptance.py` → RED
2. Mejorar mensaje de fallo
3. Ejecutar para confirmar RED
4. Implementar produccion minima (si falta)
5. GREEN → commit + push

### Slice 2: Meta-AT CLI - test_cli_disable_flag_works

**Comportamiento**: CLI debe aceptar `--no-{step}` y deshabilitar el step correspondiente.

**Ciclo**:
1. Escribir AT → RED
2. Mejorar mensaje de fallo
3. Ejecutar para confirmar RED
4. Implementar si falta
5. GREEN → commit + push

### Slice 3: Meta-AT CLI - test_cli_config_flags_propagate

**Comportamiento**: CLI debe propagar `--{step}-{field}` al config del step.

**Ciclo**:
1. Escribir AT → RED
2. Mejorar mensaje de fallo
3. Ejecutar para confirmar RED
4. Implementar si falta
5. GREEN → commit + push

### Slice 4: Meta-AT - test_cli_dry_run_no_files_created

**Comportamiento**: CLI con `--dry-run` no debe crear archivos.

**Ciclo**:
1. Escribir AT → RED
2. GREEN → commit + push

### Slice 5: Meta-AT - test_cli_output_contains_step_names

**Comportamiento**: Output del CLI debe mostrar nombres de steps ejecutados.

**Ciclo**:
1. Escribir AT → RED
2. GREEN → commit + push

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
