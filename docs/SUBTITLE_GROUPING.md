# Agrupación de Subtítulos por Oraciones

## Descripción

Esta funcionalidad implementa la lógica de agrupación de subtítulos de AssemblyAI adaptada para trabajar con los chunks de Whisper en WX3.

## Modos de Agrupación

### 1. Por Oraciones (Por Defecto) - Opción 2 de AssemblyAI

**Comando:** Sin flag o comportamiento por defecto

```bash
python wx3.py transcribe audio.mp3
python wx3.py process video.mp4 --token YOUR_TOKEN
```

**Características:**
- Agrupa chunks en segmentos basándose en oraciones completas
- **Prioridades de segmentación:**
  1. Cambio de speaker (siempre crea nuevo segmento)
  2. Fin de oración (`.`, `!`, `?`, `;`)
  3. Pausa fuerte (`,`, `:`) si excede límites de caracteres o duración
  4. Límites absolutos de caracteres o duración

**Parámetros configurables:**
- `--max-chars`: Máximo de caracteres por segmento (default: 80)
- `--max-duration`: Máxima duración en segundos por segmento (default: 10.0)

**Ejemplo:**
```bash
python wx3.py transcribe audio.mp3 --max-chars 100 --max-duration 12
```

### 2. Solo por Speaker (Segmentos Largos) - Opción 3 de AssemblyAI

**Comando:** Con flag `--long` o `-lg`

```bash
python wx3.py transcribe audio.mp3 --long
python wx3.py process video.mp4 --token YOUR_TOKEN -lg
```

**Características:**
- Agrupa chunks solo cuando cambia el speaker
- Crea segmentos más largos (todo lo que dice un speaker hasta que cambia)
- Ideal para transcripciones donde se prefiere menos fragmentación

## Arquitectura

### Módulos Nuevos

#### `sentence_grouping.py`
Contiene la lógica de agrupación adaptada de AssemblyAI:

- `is_sentence_end(text)`: Detecta fin de oración
- `is_strong_pause(text)`: Detecta pausas fuertes (coma, dos puntos)
- `group_chunks_by_sentences(chunks, max_chars, max_duration_s)`: Agrupa por oraciones
- `group_chunks_by_speaker_only(chunks)`: Agrupa solo por speaker
- `_extract_chunk_info(chunk)`: Normaliza timestamps (listas → tuplas)

### Módulos Modificados

#### `output_formatters.py`
- Actualizado `save_subtitles()` para aceptar parámetros de agrupación
- Aplica la agrupación antes de generar los archivos de salida

#### `processor.py`
- Actualizado `process_file()` para aceptar parámetros de agrupación
- Actualizado `export_results()` para pasar parámetros a `save_subtitles()`

#### `wx3.py`
- Agregados parámetros CLI: `--long/-lg`, `--max-chars`, `--max-duration`
- Comandos actualizados: `transcribe` y `process`

#### `constants.py`
- Agregado enum `GroupingMode` (str Enum):
  - `GroupingMode.sentences` = "sentences"
  - `GroupingMode.speaker_only` = "speaker-only"
- Agregadas constantes: `DEFAULT_GROUPING_MODE`, `DEFAULT_MAX_CHARS`, `DEFAULT_MAX_DURATION_S`
- Agregados mensajes de ayuda para los nuevos parámetros

**Ventajas del str Enum:**
- Type safety: El IDE puede autocompletar y validar valores
- Compatibilidad: Se puede comparar directamente con strings
- Documentación: Los valores válidos están explícitos en el código

## Tests

### `test_sentence_grouping.py`
Tests unitarios para la lógica de agrupación:
- Detección de fin de oración y pausas fuertes
- Agrupación por oraciones con diferentes escenarios
- Agrupación solo por speaker
- Manejo de límites de caracteres y duración

### `test_output_formatters.py`
Tests de integración para `output_formatters`:
- Guardado de SRT/VTT/TXT con diferentes modos de agrupación
- Respeto de límites de caracteres y duración
- Modo de agrupación por defecto

### `test_e2e_cli.py`
Tests end-to-end del CLI:
- Verificación de opciones en ayuda
- Disponibilidad de parámetros en comandos

## Desarrollo con TDD

Este desarrollo siguió estrictamente el ciclo **Red → Green → Refactor**:

1. **RED**: Se escribieron tests que fallaban
2. **GREEN**: Se implementó el código mínimo para pasar los tests
3. **REFACTOR**: Se mejoró el código manteniendo los tests verdes

### Resultados de Tests

```bash
$ python -m pytest test_sentence_grouping.py test_output_formatters.py test_e2e_cli.py -v
============================== 42 passed ==============================
```

## Ejemplos de Uso

### Transcripción simple con agrupación por oraciones
```bash
python wx3.py transcribe audio.mp3 -f srt
```

### Transcripción con segmentos largos
```bash
python wx3.py transcribe audio.mp3 -f srt --long
```

### Procesamiento completo con diarización y agrupación personalizada
```bash
python wx3.py process video.mp4 \
  --token YOUR_HF_TOKEN \
  --speaker-names "Alice,Bob" \
  --max-chars 100 \
  --max-duration 15 \
  -f srt
```

### Procesamiento con segmentos largos
```bash
python wx3.py process video.mp4 \
  --token YOUR_HF_TOKEN \
  --speaker-names "Alice,Bob" \
  --long \
  -f srt
```

### Convertir JSON intermedios a SRT/VTT

**Opción 2 (por oraciones):**
```bash
python output_convert.py transcription.json -f srt
python output_convert.py transcription.json -f vtt
```

**Opción 3 (por speaker):**
```bash
python output_convert.py transcription.json -f srt --long
python output_convert.py transcription.json -f vtt --long
```

**Con parámetros personalizados:**
```bash
python output_convert.py transcription.json -f srt \
  --max-chars 100 \
  --max-duration 15 \
  --speaker-names "Alice,Bob"
```

## Comparación con AssemblyAI

| Aspecto | AssemblyAI | WX3 |
|---------|------------|-----|
| **Input** | Palabras individuales con timestamps | Chunks de Whisper (frases) |
| **Opción 2** | `mode='sentences'` | Por defecto (sin flag) |
| **Opción 3** | `mode='speaker-only'` | `--long` / `-lg` |
| **Timestamps** | Milisegundos | Segundos (float) |
| **Speaker format** | `[Speaker] texto` | `Speaker: texto` |

## Notas Técnicas

- La agrupación se aplica **después** de la transcripción y alineación con speakers
- Los chunks originales de Whisper se mantienen intactos hasta el momento de exportación
- La lógica de agrupación es independiente del formato de salida (SRT, VTT, TXT)
- Los límites de caracteres y duración solo aplican al modo "por oraciones"
- **Timestamps normalizados**: JSON serializa tuplas como listas `[start, end]`, se normalizan automáticamente a tuplas `(start, end)` en `_extract_chunk_info()`
- **Compatibilidad**: Funciona con chunks en memoria (tuplas) y JSON deserializados (listas)
- **Type Safety**: Uso de `GroupingMode` enum en lugar de strings mágicos
- **str Enum**: `GroupingMode` hereda de `str`, permitiendo comparación directa con strings para compatibilidad
