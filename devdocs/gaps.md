# Brechas: wx41.md vs plan_wx41.md vs Implementacion

Fecha: 2026-03-02
Estado: TODAS RESUELTAS

---

## Cobertura Meta-AT vs Objetivos wx41

| Objetivo (plan_wx41.md) | Meta-AT (Dinamico Unificado) | Estado |
|--------------------------|------------------------------|--------|
| Encadenado de steps | `TestMetaAT::test_step_produces_outputs` (parametrizado) | ✅ |
| Configuracion dinamica | `TestMetaAT::test_cli_dynamic_flags` | ✅ |
| Visualizacion UI | `TestMetaAT::test_cli_output_contains_steps` | ✅ |
| Resumability (disk-based) | `TestMetaAT::test_step_resumability` | ✅ |
| Dry run | `TestMetaAT::test_cli_dry_run` | ✅ |
| Ctrl+C cleanup | (unit test en `pipeline_engine.py`) | ✅ |
| CLI Auto-discovery | `TestMetaAT::test_cli_help_shows_options` | ✅ |
| StepInfo Registry | `TestMetaAT::test_registry_has_required_fields` | ✅ |
| Fixture Real | Unificado con fixture condicional | ❌ PENDIENTE |

### Diseño: Meta-AT Unificado

```python
class TestMetaAT:
    @pytest.fixture
    def use_real_fixture(self, request):
        return request.config.getoption("--use-real-fixture", default=False)
    
    @pytest.mark.parametrize("step_name", get_all_steps().keys())
    def test_step_produces_outputs(self, step_name, tmp_path, use_real_fixture, monkeypatch):
        step_info = get_step_info(step_name)
        
        if not use_real_fixture:
            # Mock approach - create empty files
            self._setup_mock(step_name, tmp_path, monkeypatch)
        else:
            # Real fixture - use actual audio file
            self._setup_real_fixture(step_name, tmp_path)
        
        result = runner.invoke(main, [str(audio)])
        self._verify_outputs(step_name, result, tmp_path)
```

**Plan:**
1. Unificar `TestStepContract` + `TestMetaATWithRealFixture` en `TestMetaAT`
2. Agregar fixture `use_real_fixture` que alterna entre mock y real
3. Eliminar tests duplicados

---

## Resumen de Brechas Resueltas

| # | Brecha | Estado |
|---|--------|--------|
| 1 | JSON state vs file-based Ctrl+C | ✅ RESUELTA |
| 4 | "Mejor Audio" sin fallback a src | ✅ RESUELTA |
| 5 | update_ctx letra muerta | ✅ RESUELTA |
| 2 | pipeline.py → pipeline_engine.py | ✅ RESUELTA |
| 3 | metadata-driven → disk-based | ✅ RESUELTA |
| 6 | Modulos no documentados | ✅ RESUELTA |
| 7 | MediaType clase vs Enum | ✅ RESUELTA |
| 8 | Meta-AT coverage incompleto | ✅ RESUELTA |
| 9 | Meta-AT unificado con fixture real | ❌ PENDIENTE |
