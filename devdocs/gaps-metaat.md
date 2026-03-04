# BRECHA 10: Meta-AT con metadata de steps y fixture centralizado

## Estado: RESUELTA (2026-03-04)

Todos los slices implementados. Tests: 52 passed, 7 skipped (skips = fixture real no disponible en CI).

### Resultado final

- `StepInfo` tiene: `needs_audio_fixture`, `input_media_type`, `config_variants`
- MetaAT usa solo metadata del registry (sin hardcoded sets de step names)
- `audio_fixture_path` centralizado en `conftest.py`, apunta a `fixtures/sample_1m.m4a`
- `_get_all_step_variants()` genera variantes dinamicamente desde `step_info.config_variants`
- `TestStepInfoMetadata` verifica los 3 campos en GREEN

---

## Problema original

El Meta-AT tenia conocimiento interno hardcodeado de los steps:

1. `needs_real_audio = step_name in {"normalize", "srt", "transcribe", "enhance"}` en el test
2. Fixture path absoluto hardcodeado en `test_acceptance.py`
3. `StepInfo` sin metadata sobre las necesidades del step

---

## Slices completados

| Slice | Objetivo | Commit |
|-------|----------|--------|
| 1 | `needs_audio_fixture` en StepInfo | `062eba0` |
| 2 | Fixture centralizado en conftest.py | `a73abf9` |
| 3 | MetaAT usa `step_info.needs_audio_fixture` | `b94b019` |
| 4 | `input_media_type` en StepInfo | `062eba0` |
| 5 | `config_variants` en StepInfo | `062eba0` |
| 6 | `_get_all_step_variants()` desde registry | `b94b019` |

---

## Relacion con BRECHA 9

BRECHA 9: unificar tests con mocks y fixture real.
BRECHA 10: eliminar conocimiento hardcodeado del MetaAT hacia los steps.

Son complementarias - BRECHA 10 mejora la arquitectura interna del MetaAT.
