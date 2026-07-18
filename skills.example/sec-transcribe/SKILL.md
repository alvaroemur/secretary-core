---
name: sec-transcribe
description: >-
  Transcribe audio (voice notes, WhatsApp PTT, .ogg/.mp3/.m4a/.wav) to text via the
  secretary-core Whisper script. Use when the user drops an audio file or asks to
  "transcribe", "pasar a texto", "qué dice este audio".
---

# sec-transcribe — audio → texto

**Mission:** convertir audio a texto usando el transcriptor del engine (secretary-core), sin reinventar el pipeline.

## Guardrails

- No hay binario local — usa la API de OpenAI Whisper (`whisper-1`) vía el engine; requiere `OPENAI_API_KEY`.
- No mover ni borrar el audio original.
- Transcripción cruda = insumo; anclar a memoria es trabajo de `sec-write` / `wiki-update`, no de este skill.

## Setup

```bash
export SECRETARY_CORE="${SECRETARY_CORE:-$HOME/Dev/secretary-core}"
test -n "$OPENAI_API_KEY" || echo "⚠️ Falta OPENAI_API_KEY"
```

## Loop

1. Resolver ruta absoluta del audio (comillas si hay espacios).
2. Correr:

```bash
cd "$SECRETARY_CORE/whatsapp/src"
npx tsx transcribe.ts -i "<ruta>" -l es
```

3. Batch del inbox WhatsApp sin transcribir: `npx tsx transcribe.ts --all-missing`
4. Leer el `.txt` / capturar stdout y devolver el texto.

## Flags

| Flag | Descripción |
|------|-------------|
| `-i <ruta>` | Audio de entrada (ruta absoluta) |
| `-l <lang>` | Idioma (default `es`) |
| `--model <m>` | Modelo Whisper (default `whisper-1`) |
| `--all-missing` | Batch: transcribe todo el inbox/media sin `.txt` |

## Salida

- Audios en `inbox/media` → escribe `.txt` espejo en `inbox/transcripts/`.
- Audio suelto (p. ej. Downloads) → solo stdout (capturarlo). ⚠️ conocido: el `.txt` del script queda en ruta relativa rara para audios fuera de `media/` (ver issue del engine).
- Reporte inline: `🎙️ **Transcrito** · <archivo> (<n> chars)` + texto.

## Notas

- Script en el engine (código), no en `.secretary` (datos).
- Si falta `OPENAI_API_KEY`, el script sale con error.
