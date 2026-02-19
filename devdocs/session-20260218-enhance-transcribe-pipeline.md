# Sesión 2026-02-18: Pipeline enhance → transcribe → SRT → video

## Contexto

Construcción del pipeline completo para procesar reuniones grabadas (audio/video):
enhance → transcribe (AssemblyAI) → SRT → MP4 de salida.

---

## Lecciones de tecnología

### ClearVoice: FRCRN_SE_16K vs MossFormer2_SE_48K

**Problema detectado experimentalmente:**
FRCRN_SE_16K (el modelo "estándar") fue diseñado para un único hablante cercano al micrófono.
En grabaciones de sala con múltiples hablantes a distintas distancias:
- Suprime voces lejanas como si fueran ruido de sala
- Colapsa 4-5 hablantes a solo 2 en la diarización posterior
- Eliminó un segmento completo de ~10 segundos de un hablante lejano

**Solución:**
`MossFormer2_SE_48K` es el modelo correcto para reuniones multi-hablante:
- Opera a 48kHz (mayor resolución → preserva mejor voces lejanas)
- Recupera el segmento perdido que FRCRN borraba
- Detecta 4 hablantes vs 2 de FRCRN (en el mismo audio)
- Recupera el primer fragmento breve del inicio que FRCRN cortaba
- La extracción previa debe ser a 48kHz (`-ar 48000`), no 16kHz

**Comparativa de modelos disponibles (speech_enhancement):**
| Modelo | Hz | Mejor para |
|---|---|---|
| FRCRN_SE_16K | 16k | Un hablante, micrófono cercano |
| MossFormer2_SE_48K | 48k | Reuniones multi-hablante, sala |
| MossFormerGAN_SE_16K | 16k | No probado en este contexto |

### AssemblyAI: formato de subida

Subir WAV de 48kHz sin comprimir es innecesario:
- 5 min de reunión = ~27 MB WAV vs ~3-4 MB AAC
- AssemblyAI acepta M4A/AAC directamente con igual calidad de transcripción
- El pipeline ahora convierte a AAC 192k tras el enhance antes de subir

### ffmpeg-python: patrones de uso

```python
# Flag sin valor (ej: -shortest)
ffmpeg.output(..., shortest=None)

# Multiple inputs con selección de stream
ffmpeg.output(input1.video, input2.audio, "out.mp4", vcodec="copy", acodec="copy")

# lavfi para video generado
ffmpeg.input("color=c=black:s=854x480:r=30", f="lavfi")

# GPU hwaccel en extracción (intento con fallback)
inp = ffmpeg.input(str(src), hwaccel="cuda") if _GPU else ffmpeg.input(str(src))

# Captura de stderr para LUFS (retorna bytes)
_, stderr = ffmpeg.input(...).output("-", format="null", af="loudnorm=print_format=json").run(capture_stderr=True)
m = re.search(rb'"input_i"\s*:\s*"([^"]+)"', stderr)
```

### GPU: detección unificada

Usar siempre `torch.cuda.is_available()` como fuente única de verdad para GPU.
- torch ya está en el entorno (requerido por ClearVoice/MossFormer)
- NVENC de ffmpeg y PyTorch CUDA son independientes; el script prueba NVENC y hace fallback a CPU si falla
- Centralizar en `enhance_audio._GPU` e importar desde ahí evita duplicación

```python
# enhance_audio.py — fuente canónica
_GPU = torch.cuda.is_available()

# otros scripts
from enhance_audio import _GPU
```

### NVENC: preset más rápido

Para video de contenido trivial (video negro):
- `h264_nvenc -preset p1` = preset más rápido de NVENC (escala p1..p7)
- Para CPU fallback: `libx264 -preset ultrafast`
- No usar `-tune` para este caso de uso

---

## Lecciones de diseño de software

### Arquitectura del pipeline

**Patrón establecido:** cada paso es una función importable + CLI independiente.

```
enhance_audio.process()           <- unidad atómica de enhance (audio)
enhance_video_audio.process_video() <- unidad atómica de enhance (video)
assembly_transcribe.transcribe_file() <- unidad atómica de transcripción
assemblyai_json_to_srt.words_to_srt() <- unidad atómica de SRT
convert_audio_to_mp4.convert()    <- unidad atómica de video
enhance_and_transcribe.py         <- orquestador
```

Beneficio: cada función es testeable y reutilizable independientemente.

### Funciones transcribe_file() vs transcribe()

La función original `transcribe()` devolvía solo string TXT.
Refactorización: `transcribe_file()` guarda TXT + JSON de timestamps word-level:
```python
[{"text": "palabra", "start": 0, "end": 500, "confidence": 0.98, "speaker": "A"}, ...]
```
El JSON es el contrato de datos entre transcripción y generación de SRT/subtítulos.

### Defaults orientados al uso real

- **AAC por defecto, WAV como override** (`--wav`): reduce tamaño de archivos sin pérdida perceptible
- **Auto-detect idioma y hablantes**: menos fricción, el usuario solo especifica cuando sabe
- **Cache de enhance**: la operación costosa (~9 min para 60 min de audio) solo corre una vez
- **Lazy loading de ClearVoice**: no cargar el modelo si `--skip-enhance`

### Aliases para compatibilidad

Al renombrar funciones, dejar alias:
```python
extract_to_wav16k = extract_to_wav   # nombre viejo -> nueva implementación
to_m4a = to_aac                       # nombre viejo -> nueva implementación
```
Esto permite cambiar nombres sin romper imports externos ni enhance_video_audio.py.

### Fallback GPU en ffmpeg

Probar CUDA primero y caer a CPU si falla, sin abortar el proceso:
```python
def extract_to_wav(src, dst):
    def _attempt(use_gpu):
        try:
            inp = ffmpeg.input(str(src), hwaccel="cuda") if use_gpu else ffmpeg.input(str(src))
            ...
            return True
        except ffmpeg.Error:
            return False
    return (_GPU and _attempt(True)) or _attempt(False)
```

---

## Preferencias del usuario

### Código Python en Windows

- **Sin caracteres Unicode** en ningún string que pueda imprimirse (print, argparse, f-strings, docstrings)
  - La consola Windows usa cp1252; `→`, `─`, `é`, `á` etc. rompen con UnicodeEncodeError
  - Reemplazar: `->` en lugar de `→`, sin acentos en strings de output
- **Sin `> NUL`** en Git Bash: crea un archivo físico llamado "nul" (nombre reservado Windows)
  - Usar siempre `> /dev/null` o `2>/dev/null`

### Flujo de trabajo

- Commit + push tras cada conjunto de cambios significativos
- Los scripts deben ser usables como CLI independiente Y como módulo importable
- Preferencia por defaults prácticos sobre opciones explícitas

### Estructura de salida

Archivos de salida siempre junto al archivo de entrada (mismo directorio):
```
reunion.mp4
reunion_audio_enhanced.m4a
reunion_audio_enhanced_transcript.txt
reunion_audio_enhanced_timestamps.json
reunion_audio_enhanced_timestamps.srt
reunion_audio_enhanced_video.mp4      (con --videooutput)
```

### CLI design

- Flags negativos para overrides de defaults: `--wav` (no `--m4a`), `--skip-enhance`
- `--force` para ignorar cache
- Labels informativos en output: mostrar modelo, GPU/CPU, idioma
