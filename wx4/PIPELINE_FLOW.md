# wx4 Pipeline Flow Diagram

## Full Pipeline (default - no flags)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           wx4 Pipeline                                        │
└─────────────────────────────────────────────────────────────────────────────────┘

Input: [audio/video file]

    │
    ▼
┌─────────────────────┐
│   cache_check_step  │  ←── Si existe cache: salta a transcribe
│   (cache_hit)       │      Usa: --force para ignorar cache
└─────────────────────┘
    │
    │ cache_hit=False
    ▼
┌─────────────────────┐     ┌─────────────────────────────────────────────┐
│   normalize_step    │     │ 1. extract_to_wav (src → tmp_raw.wav)     │
│   (--no-normalize) │     │ 2. normalize_lufs (tmp_raw → tmp_norm)     │
│                     │     │ 3. to_aac (tmp_norm → _normalized.m4a)    │
│ FLAGS:              │     │                                             │
│ --no-normalize      │     │ OUTPUT: ctx.normalized = *_normalized.m4a  │
└─────────────────────┘     └─────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────┐     ┌─────────────────────────────────────────────┐
│   enhance_step      │     │ 1. apply_clearvoice (normalized→tmp_enh)    │
│   (--no-enhance)   │     │ 2. to_aac (tmp_enh → _enhanced.m4a)        │
│                     │     │                                             │
│ FLAGS:              │     │ INPUT: ctx.normalized o ctx.src            │
│ --no-enhance       │     │ OUTPUT: ctx.enhanced = *_enhanced.m4a      │
└─────────────────────┘     └─────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────┐
│   cache_save_step   │  ←── Guarda *_enhanced.m4a en cache
└─────────────────────┘
    │
    ▼
┌─────────────────────┐
│   transcribe_step   │  ←── INPUT: ctx.enhanced > ctx.normalized > ctx.src
│                     │
│ BACKEND:           │
│ --backend          │
│ --assemblyai-key  │
│ --whisper-*        │
└─────────────────────┘
    │
    ▼
┌─────────────────────┐
│     srt_step        │  ←── Genera archivo .srt
│                     │
│ FLAGS:             │
│ --srt-mode         │
│ --speakers         │
│ --speakers-map     │
│ --language         │
└─────────────────────┘
    │
    ▼
┌─────────────────────┐
│    video_step       │  ←── (--video-output)
│   (optional)        │     Genera video con audio transcrito
│                     │     INPUT: ctx.enhanced > ctx.normalized > ctx.src
└─────────────────────┘
    │
    ▼
┌─────────────────────┐
│  compress_step      │  ←── (--compress 0.4)
│   (optional)        │     Comprime video de salida
└─────────────────────┘
    │
    ▼
Output: [*.srt, *.mp4 (optional), *.mp4 (compressed, optional)]


═══════════════════════════════════════════════════════════════════════════════════

## Flag Combinations

┌─────────────────┬──────────────────────────────────────────────────────────────┐
│ FLAGS           │ PIPELINE STEPS ACTIVE                                       │
├─────────────────┼──────────────────────────────────────────────────────────────┤
│ (none)          │ cache_check → normalize → enhance → cache_save →           │
│                 │ transcribe → srt → [video] → [compress]                   │
├─────────────────┼──────────────────────────────────────────────────────────────┤
│ --no-normalize  │ cache_check → enhance → cache_save →                       │
│                 │ transcribe → srt → [video] → [compress]                    │
├─────────────────┼──────────────────────────────────────────────────────────────┤
│ --no-enhance    │ cache_check → normalize → cache_save →                     │
│                 │ transcribe → srt → [video] → [compress]                   │
├─────────────────┼──────────────────────────────────────────────────────────────┤
│ --no-normalize  │ transcribe → srt → [video] → [compress]                   │
│ --no-enhance    │                                                              │
├─────────────────┼──────────────────────────────────────────────────────────────┤
│ --force         │ Ignora cache, reprocesa todo                                │
└─────────────────┴──────────────────────────────────────────────────────────────┘


═══════════════════════════════════════════════════════════════════════════════════

## Audio Source Priority for Transcription

                    ┌─────────────────┐
                    │   transcribe    │
                    │     step        │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              ▼              ▼
     ┌────────────┐ ┌────────────┐ ┌────────────┐
     │ ctx.enhanced│ │ctx.normalized│ │  ctx.src   │
     │ (preferido)│ │ (si no hay  │ │ (fallback) │
     │            │ │  enhanced)  │ │            │
     └────────────┘ └────────────┘ └────────────┘

  Priority: --no-enhance=false → enhanced
            --no-enhance=true + --no-normalize=false → normalized  
            --no-enhance=true + --no-normalize=true → src
