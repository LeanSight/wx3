# Plan: wx4 - ATDD + TDD Strict, One-Piece Flow

## Protocolo: RED -> GREEN -> REFACTOR por pieza

Para cada pieza:
1. Escribir SOLO el test file (pytest confirma RED)
2. Escribir implementacion minima para que pase (pytest confirma GREEN)
3. Refactorizar si hay oportunidad clara (pytest confirma GREEN)
4. Solo entonces avanzar a la siguiente pieza

---

## Estado de avance

| # | Pieza                  | Test file                    | Impl file                    | Estado   |
|---|------------------------|------------------------------|------------------------------|----------|
| 0 | ATDD acceptance        | tests/test_acceptance.py     | (todos los modulos)          | RED - pendiente GREEN final |
| 1 | conftest               | tests/conftest.py            | (fixtures)                   | DONE     |
| 2 | context                | tests/test_context.py        | context.py                   | GREEN    |
| 3 | speakers               | tests/test_speakers.py       | speakers.py                  | GREEN    |
| 4 | cache_io               | tests/test_cache_io.py       | cache_io.py                  | GREEN    |
| 5 | grouping               | tests/test_grouping.py       | common/grouping.py           | GREEN    |
| 6 | format_convert         | tests/test_format_convert.py | format_convert.py            | GREEN    |
| 7 | audio_extract          | tests/test_audio_extract.py  | audio_extract.py             | GREEN    |
| 8 | audio_normalize        | tests/test_audio_normalize.py| audio_normalize.py           | GREEN    |
| 9 | audio_enhance          | tests/test_audio_enhance.py  | audio_enhance.py             | GREEN    |
|10 | audio_encode           | tests/test_audio_encode.py   | audio_encode.py              | GREEN    |
|11 | video_black            | tests/test_video_black.py    | video_black.py               | GREEN    |
|12 | video_merge            | tests/test_video_merge.py    | video_merge.py               | GREEN    |
|13 | format_srt             | tests/test_format_srt.py     | format_srt.py                | GREEN    |
|14 | transcribe_aai         | tests/test_transcribe_aai.py | transcribe_aai.py            | GREEN    |
|15 | steps                  | tests/test_steps.py          | steps.py                     | GREEN    |
|16 | pipeline               | tests/test_pipeline.py       | pipeline.py                  | GREEN    |
|17 | cli                    | tests/test_cli.py            | cli.py                       | GREEN    |
|18 | ATDD GREEN             | tests/test_acceptance.py     | (todos GREEN)                | GREEN    |

---

## Estructura de directorios

```
wx3/
  common/
    __init__.py
    types.py
    grouping.py

  wx4/
    __init__.py
    context.py
    speakers.py
    cache_io.py
    audio_extract.py
    audio_normalize.py
    audio_enhance.py
    audio_encode.py
    format_convert.py
    format_srt.py
    transcribe_aai.py
    video_black.py
    video_merge.py
    steps.py          <- PENDIENTE
    pipeline.py       <- PENDIENTE
    cli.py            <- PENDIENTE

    tests/
      __init__.py
      conftest.py
      test_acceptance.py
      test_context.py
      test_speakers.py
      test_cache_io.py
      test_grouping.py
      test_format_convert.py
      test_audio_extract.py
      test_audio_normalize.py
      test_audio_enhance.py
      test_audio_encode.py
      test_video_black.py
      test_video_merge.py
      test_format_srt.py
      test_transcribe_aai.py
      test_steps.py     <- PENDIENTE
      test_pipeline.py  <- PENDIENTE
      test_cli.py       <- PENDIENTE
```

---

## Grafo de dependencias

```
Nivel 0 (sin deps):  common/types.py, wx4/context.py
Nivel 1 (puras):     wx4/speakers.py, wx4/format_convert.py
Nivel 2 (IO local):  wx4/cache_io.py, common/grouping.py
Nivel 3 (ffmpeg):    wx4/audio_extract.py, audio_normalize.py,
                     audio_encode.py, video_black.py, video_merge.py
Nivel 4 (duck-type): wx4/audio_enhance.py
Nivel 5 (compuesta): wx4/format_srt.py
Nivel 6 (API ext):   wx4/transcribe_aai.py
Nivel 7 (orquesta):  wx4/steps.py
Nivel 8:             wx4/pipeline.py
Nivel 9:             wx4/cli.py
```

---

## Spec: Pieza 15 - steps.py

```
TestCacheCheckStep:
  test_miss_when_src_not_in_cache
  test_hit_when_src_in_cache
  test_force_flag_causes_miss_even_if_in_cache
  test_timing_recorded_in_context

TestCacheSaveStep:
  test_saves_when_enhanced_and_no_hit
  test_skips_when_cache_hit_true
  test_skips_when_enhanced_is_none
  test_timing_recorded

TestEnhanceStep:
  test_returns_cached_path_on_hit
  test_calls_extract_normalize_enhance_encode_on_miss
  test_raises_when_extract_fails
  test_raises_when_encode_fails
  test_timing_recorded

TestTranscribeStep:
  test_uses_enhanced_path_when_set
  test_uses_src_when_enhanced_is_none
  test_sets_transcript_txt_and_json_on_ctx
  test_timing_recorded

TestSrtStep:
  test_raises_when_transcript_json_is_none
  test_reads_json_and_calls_words_to_srt
  test_sets_srt_on_ctx
  test_timing_recorded

TestVideoStep:
  test_uses_enhanced_audio_when_available
  test_raises_when_audio_to_black_video_returns_false
  test_sets_video_out_on_ctx
  test_timing_recorded
```

## Spec: Pieza 16 - pipeline.py

```
TestPipeline:
  test_empty_steps_returns_context_unchanged
  test_single_step_applied
  test_steps_applied_in_order
  test_exception_from_step_propagates

TestBuildSteps:
  test_default_has_cache_check_enhance_cache_save_transcribe_srt
  test_skip_enhance_removes_cache_and_enhance_steps
  test_videooutput_appends_video_step
  test_force_cache_prepends_inject_step
  test_all_flags_combined
```

## Spec: Pieza 17 - cli.py

```
TestCli:
  test_unknown_file_prints_error
  test_calls_pipeline_run_once_per_file
  test_skip_enhance_flag_forwarded
  test_videooutput_flag_forwarded
  test_force_flag_forwarded
  test_speaker_names_parsed_and_forwarded
  test_summary_table_in_output
```
