# Integracion wx3 en wx4: analisis de brecha

Objetivo: agregar Whisper + PyAnnote (el motor local de wx3) como backend alternativo
al pipeline wx4, manteniendo AssemblyAI como default y sin romper nada existente.

Resultado esperado: pipeline 100% local (ClearVoice -> Whisper + PyAnnote),
sin dependencia de APIs de pago.

---

## 1. Diferencias de formato de datos

### 1.1 Formato JSON del transcript

wx4 (AssemblyAI) guarda `_timestamps.json` como lista de PALABRAS:

```json
[{"text": "hello", "start": 0, "end": 500, "confidence": 0.99, "speaker": "A"}]
```

- Unidad: palabra individual (word-level)
- Timestamps: milliseconds (int)
- Speaker: etiquetas cortas AssemblyAI ("A", "B", "C")

wx3 (Whisper) produce lista de CHUNKS (frases de varias palabras):

```python
[{"text": " hello world", "timestamp": (0.0, 2.5), "speaker": "SPEAKER_00"}]
```

- Unidad: frase (chunk-level, tipicamente 3-10 palabras)
- Timestamps: segundos (float tuple)
- Speaker: etiquetas PyAnnote ("SPEAKER_00", "SPEAKER_01")

**Conversion necesaria** (wx3 -> formato wx4):

```python
def whisper_chunks_to_wx4_words(chunks):
    return [
        {
            "text": c["text"].strip(),
            "start": int(c["timestamp"][0] * 1000),
            "end": int(c["timestamp"][1] * 1000),
            "confidence": 1.0,            # Whisper no da confianza por chunk
            "speaker": c.get("speaker"),
        }
        for c in chunks
        if c["timestamp"][0] is not None and c["timestamp"][1] is not None
    ]
```

El resto del pipeline wx4 (format_srt.py, srt_step, etc.) no necesita cambios.

### 1.2 Etiquetas de speaker

| Backend       | Formato          | Ejemplo              |
|---------------|------------------|----------------------|
| AssemblyAI    | letra suelta     | "A", "B", "C"        |
| PyAnnote      | SPEAKER_NN       | "SPEAKER_00", "SPEAKER_01" |

El campo `speaker_names` en PipelineContext ya es un dict str->str, compatible con
ambos formatos. Solo cambia la clave que el usuario debe usar en `--speakers-map`.

No hay breaking change en la logica, pero si en el UX: el usuario debe saber que
con backend=assemblyai usa "A=Marcel" y con backend=whisper usa "SPEAKER_00=Marcel".

---

## 2. Audio loading: sin brecha

wx4 enhance_step produce un archivo .m4a en disco.

wx3 transcription necesita `{"waveform": tensor, "sample_rate": 16000}` via
`input_media.load_media()`.

`input_media.load_media()` carga .m4a via PyAV (ya soportado). El archivo de salida
de ClearVoice es directamente consumible por wx3. No hay conversion necesaria.

---

## 3. Acoplamiento Diarization + Transcription

**AssemblyAI**: diarization + transcription en UNA llamada a la API. El servidor
devuelve palabras ya etiquetadas con speaker. El step `transcribe_step` actual
devuelve (txt_path, json_path) con todo integrado.

**wx3 (local)**: son DOS operaciones separadas:
1. `perform_diarization()` -> lista de segmentos {start, end, speaker}
2. `perform_transcription()` -> chunks {text, timestamp}
3. `align_diarization_with_transcription()` -> chunks con speaker asignado

Esto implica DOS nuevos steps en el pipeline wx4:

```
... -> diarize_wx3_step -> transcribe_whisper_step -> srt_step -> ...
```

Con sus output_fn declarados para que el skip/resume logic funcione:

```python
_DIARIZATION_JSON = lambda ctx: (ctx.enhanced or ctx.src).parent / f"{(ctx.enhanced or ctx.src).stem}_diarization.json"
_TRANSCRIPT_JSON  = lambda ctx: (ctx.enhanced or ctx.src).parent / f"{(ctx.enhanced or ctx.src).stem}_timestamps.json"
```

Si `_diarization.json` ya existe -> diarize_wx3_step se saltea.
Si `_timestamps.json` ya existe -> transcribe_whisper_step se saltea.
Esto es consistente con el mecanismo de resume ya implementado en v2.

Alternativa descartada: un solo step que hace diarize+transcribe+align internamente.
Descartada porque no permite skip granular (si la diarizacion ya esta lista pero
la transcripcion no, habria que re-diarizar de todas formas).

---

## 4. Campos nuevos en PipelineContext

```python
@dataclass
class PipelineContext:
    ...
    # --- campos existentes (sin cambios) ---
    language: Optional[str] = None
    speakers: Optional[int] = None
    speaker_names: Dict[str, str] = field(default_factory=dict)
    force: bool = False

    # --- nuevos campos para backend wx3 ---
    transcribe_backend: str = "assemblyai"          # "assemblyai" | "whisper"
    hf_token: Optional[str] = None                  # HuggingFace token para PyAnnote
    device: str = "auto"                            # auto/cpu/cuda/mps
    whisper_model: str = "openai/whisper-large-v3"
    batch_size: int = 8
    chunk_length: int = 8
    attn_type: str = "sdpa"                         # sdpa/eager/flash_attention_2
    skip_diarization: bool = False                  # solo Whisper sin PyAnnote
```

Los campos nuevos tienen defaults que mantienen el comportamiento actual cuando
`transcribe_backend="assemblyai"`.

---

## 5. Nuevo modulo: wx4/transcribe_wx3.py

Interfaz identica a `transcribe_assemblyai()` para que `transcribe_step`
sea agnóstico al backend:

```python
def transcribe_with_whisper(
    audio: Path,
    lang: Optional[str] = None,
    speakers: Optional[int] = None,
    hf_token: Optional[str] = None,
    device: str = "auto",
    whisper_model: str = "openai/whisper-large-v3",
    batch_size: int = 8,
    chunk_length: int = 8,
    attn_type: str = "sdpa",
    diar_segments: Optional[List[Dict]] = None,    # pre-loaded if diarize was separate
) -> Tuple[Path, Path]:
    """
    Returns (txt_path, json_path) identico a transcribe_assemblyai().
    json_path contiene lista en formato wx4: [{text, start_ms, end_ms, speaker}, ...]
    """
```

Internamente:
1. `load_media(audio)` -> waveform tensor
2. `get_transcription_pipeline(whisper_model, device)` -> Whisper pipeline [cached]
3. `perform_transcription(audio_data, lang, chunk_length, batch_size)`
4. Si `diar_segments` no es None: `align_diarization_with_transcription(diar_segments, chunks)`
5. `whisper_chunks_to_wx4_words(chunks)` -> conversion de formato
6. Atomic write a `_timestamps.json.tmp` -> rename

---

## 6. Nuevo step: diarize_wx3_step

```python
def diarize_wx3_step(ctx: PipelineContext) -> PipelineContext:
    """
    Run PyAnnote diarization. Saves _diarization.json to disk.
    Sets ctx.diarization_json on the returned context.
    """
    audio = ctx.enhanced if ctx.enhanced is not None else ctx.src
    from diarization import perform_diarization, format_diarization_result
    from pipelines import get_diarization_pipeline
    from input_media import load_media

    pipeline = get_diarization_pipeline(hf_token=ctx.hf_token, device=ctx.device)
    audio_data = load_media(audio, device=ctx.device)
    result = perform_diarization(audio_data, pipeline, ctx.speakers)
    segments = format_diarization_result(result)["speakers"]

    out = audio.parent / f"{audio.stem}_diarization.json"
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(segments, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.rename(out)

    return dataclasses.replace(ctx, diarization_json=out, timings={...})
```

Necesita un campo nuevo en PipelineContext: `diarization_json: Optional[Path] = None`.

---

## 7. Adaptacion de transcribe_step

Dos opciones:

**Opcion A (recomendada): strategy via ctx**

```python
def transcribe_step(ctx: PipelineContext) -> PipelineContext:
    audio = ctx.enhanced if ctx.enhanced is not None else ctx.src
    if ctx.transcribe_backend == "whisper":
        diar_segments = _load_diar_segments(ctx.diarization_json)
        txt_path, json_path = transcribe_with_whisper(
            audio, ctx.language, ctx.speakers, ctx.hf_token,
            ctx.device, ctx.whisper_model, ctx.batch_size,
            ctx.chunk_length, ctx.attn_type, diar_segments,
        )
    else:  # assemblyai (default)
        txt_path, json_path = transcribe_assemblyai(audio, ctx.language, ctx.speakers)
    ...
```

Ventaja: un solo step visible, la logica del backend es interna.
Sin cambios en build_steps() ni en el output_fn de transcribe.

**Opcion B: steps separados por backend**

`build_steps()` acepta `backend` param y agrega los steps correspondientes.

Ventaja: mas granular (diarize y transcribe son skipables por separado).
Desventaja: cambia la firma de build_steps() y la cantidad de steps visibles.

La Opcion A es mas simple y mantiene la interfaz existente intacta.
La Opcion B se puede implementar como refinamiento posterior.

---

## 8. Dependencias de wx3 desde wx4

Los modulos de wx3 son planos en el root del proyecto (sin package):
- `transcription.py`
- `diarization.py`
- `alignment.py`
- `pipelines.py`
- `input_media.py`
- `constants.py` (wx3 constants, distinto de cualquier constante de wx4)
- `lazy_loading.py`

El root esta en sys.path (via pytest rootdir y via `_wx3.pth`), asi que son
importables directamente desde wx4.

**Riesgo de colision de nombres**: ninguno detectado. Los modulos wx3 tienen nombres
que no chocan con los de wx4 (que tiene prefijo wx4/ como package).

**Dependencias pesadas que se cargan al importar transcribe_wx3.py**:
- `torch` (via lazy_loading, solo en primer uso)
- `transformers` (Whisper, via lazy_loading)
- `pyannote.audio` (via lazy_loading)

El patron lazy_loading de wx3 ya evita que estos imports ralenticen la CLI si el
backend no se usa.

---

## 9. Cambios en CLI (wx4/cli.py)

```bash
# Backend selector
python -m wx4 audio.mp4 --backend assemblyai   # default, igual que hoy
python -m wx4 audio.mp4 --backend whisper       # nuevo

# Opciones solo para backend whisper
python -m wx4 audio.mp4 --backend whisper \
  --device cuda \
  --model openai/whisper-large-v3 \
  --batch-size 8 \
  --chunk-length 8 \
  --attn-type sdpa \
  --skip-diarization    # solo Whisper, sin PyAnnote (sin speaker labels)

# HF_TOKEN: via env var HF_TOKEN (igual que wx3)
```

Los flags nuevos solo se validan/usan cuando `--backend whisper`. Si se pasan
con `--backend assemblyai`, se ignoran con un warning.

---

## 10. Cambios en build_steps()

```python
def build_steps(
    skip_enhance: bool = False,
    videooutput: bool = False,
    force: bool = False,
    backend: str = "assemblyai",      # NUEVO
    skip_diarization: bool = False,   # NUEVO
) -> List[NamedStep]:
    ...
    if backend == "whisper" and not skip_diarization:
        steps.append(NamedStep("diarize", diarize_wx3_step, _DIARIZATION_JSON))
    steps.append(NamedStep("transcribe", transcribe_step, _TRANSCRIPT_JSON))
    ...
```

---

## 11. Resumen de archivos que cambian

| Archivo                     | Tipo de cambio                                      |
|-----------------------------|-----------------------------------------------------|
| wx4/context.py              | +7 campos: transcribe_backend, hf_token, device, whisper_model, batch_size, chunk_length, attn_type, skip_diarization, diarization_json |
| wx4/pipeline.py             | build_steps() acepta backend + skip_diarization; agrega _DIARIZATION_JSON lambda |
| wx4/steps.py                | transcribe_step ramifica en backend; nuevo diarize_wx3_step |
| wx4/cli.py                  | nuevos flags --backend, --device, --model, --batch-size, --chunk-length, --attn-type, --skip-diarization |
| wx4/transcribe_wx3.py       | NUEVO: wrapper Whisper + PyAnnote con interfaz compatible |
| wx4/format_convert.py       | +whisper_chunks_to_wx4_words() conversion |
| wx4/tests/test_context.py   | tests de nuevos campos                              |
| wx4/tests/test_pipeline.py  | tests de build_steps con backend=whisper            |
| wx4/tests/test_steps.py     | tests de diarize_wx3_step y transcribe_step con ambos backends |
| wx4/tests/test_transcribe_wx3.py | NUEVO: tests de transcribe_with_whisper()      |
| wx4/tests/test_cli.py       | tests de nuevos flags                               |

Archivos que NO cambian:
- format_srt.py (ya funciona con el formato de chunks)
- transcribe_aai.py (sin cambios)
- srt_step, srt_step, video_step (sin cambios)
- cache_io.py, audio_encode.py, etc. (sin cambios)

---

## 12. Orden de implementacion (TDD, one-piece flow)

| # | Pieza                              | Tests primero en                    |
|---|------------------------------------|-------------------------------------|
| 1 | whisper_chunks_to_wx4_words()      | test_format_convert.py              |
| 2 | PipelineContext nuevos campos      | test_context.py                     |
| 3 | transcribe_with_whisper() (mock)   | test_transcribe_wx3.py              |
| 4 | diarize_wx3_step                   | test_steps.py                       |
| 5 | transcribe_step con backend branch | test_steps.py                       |
| 6 | build_steps() con backend param    | test_pipeline.py                    |
| 7 | CLI nuevos flags                   | test_cli.py                         |

Los tests de transcribe_wx3.py mockean los modulos de wx3 (lazy_load, perform_transcription,
perform_diarization) igual que test_transcribe_aai.py mockea el modulo aai.
No se requiere hardware real para correr la suite.

---

## 13. Compatibilidad retroactiva

- `transcribe_backend="assemblyai"` es el default -> comportamiento actual sin cambios
- Tests existentes: 191 tests siguen pasando sin modificacion (los nuevos campos tienen defaults)
- CLI: `python -m wx4 file.mp4` (sin --backend) = comportamiento actual
- output files: los nombres no cambian (mismos lambdas _TRANSCRIPT_JSON, _SRT_OUT, etc.)
