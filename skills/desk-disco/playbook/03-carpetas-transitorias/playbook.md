# Fase 3 — Escritorio, Downloads, Documents

Fuente de verdad: `~/.secretary/operational/orden-local.md` (mapa de destinos, carpetas
transitorias estándar, ventanas de retención). Este archivo es el **cómo ejecutar** esa política
en una corrida a fondo; no dupliques la taxonomía aquí — léela desde ahí cada vez
(`secretary config path operational.orden_local`).

## 3.1 Escritorio — screenshots sueltos

1. Listar `Screenshot *.png` sueltos (no en subcarpetas ya organizadas).
2. Clasificar por proyecto **leyendo la imagen** (Read tool o subagente Haiku si son muchos —
   ver `04-migracion-drive` para cuándo delegar a subagente). Mapa de señales visuales →
   proyecto: mismo que la tabla de `orden-local.md` §2, aplicado a contenido de pantalla en vez
   de nombre de archivo.
3. Mover a `<proyecto>/capturas/` en Cowork. Sin match claro → `~/Desktop/_tmp/`.
4. Si una carpeta de capturas de proyecto vive en el Escritorio (p. ej. `tutorial <cliente>`),
   migrarla a `capturas/` del proyecto y dejar un **symlink** en el Escritorio con el mismo
   nombre, para que screenshots nuevos sigan cayendo ahí sin fricción:
   ```bash
   ln -s "<ruta-destino-en-cowork>" "$HOME/Desktop/<nombre-original>"
   ```
5. Screenshots de los últimos 7 días son trabajo en curso — no forzar su clasificación, quedan
   sueltos hasta la siguiente corrida.

## 3.2 Downloads — clasificación por procedencia

1. Usar el inventario de fase 1 (`mdls kMDItemWhereFroms` + fecha) para rutear cada archivo suelto
   contra el mapa de `orden-local.md` §2.
2. Instaladores (`.dmg`, `.pkg`) sueltos en la raíz → mover a `Downloads/_instaladores/`
   directamente (no requiere el mapa de proyectos).
3. Zips que sean re-descargas de Drive ya procesadas (nombre tipo `drive-download-*`,
   `*-3-001.zip` de exports de Sheets/Docs) → si el contenido ya vive en su destino en Cowork,
   proponer borrado en vez de mover.
4. Todo lo que no matchea → carpeta transitoria correspondiente (`_fotos`, `_whatsapp`, `_libros`,
   `_transcripciones`, `_riverside`) o `_tmp` si no hay categoría. **No inventar carpetas de
   proyecto nuevas** sin verificar que el proyecto existe en `~/Cowork/*/proyectos/`.

## 3.3 Retención de carpetas transitorias — aplicar, no asumir

Antes de proponer un borrado, verificar la condición de la política, no solo la edad:

| Carpeta | Verificación antes de proponer borrado |
|---|---|
| `_instaladores/` | ninguna — instaladores >30 días son candidatos directos |
| `_fotos/` | ¿están en Google Photos o ya se subieron a Drive? Si no se sabe, preguntar antes de borrar (dato personal irreemplazable) |
| `_whatsapp/` | >60 días sin abrir — proponer, no ejecutar (puede haber contexto de conversación aún relevante) |
| `_libros/` | `sqlite3 ~/Documents/calibre/metadata.db "SELECT title FROM books;"` — solo lo ya importado es candidato a borrado directo; el resto se pregunta |
| `_transcripciones/` | ¿el proyecto al que pertenece ya tiene la transcripción en su memoria/wiki? Si sí, proponer borrado |
| `_riverside/` | ¿ya está en la carpeta Drive del podcast? Ver fase 4 — si no, subir primero |

**Regla dura:** ningún archivo con contenido personal, financiero o de negocio se borra sin
`AskUserQuestion` explícito, aunque cumpla la ventana de retención. La retención decide qué se
**propone**, no qué se ejecuta directo — la única excepción es lo puramente regenerable (fase 2)
y las credenciales sueltas (fase 0, siempre 🚨).

## 3.4 Batching de preguntas

Agrupar todas las decisiones ambiguas de esta fase en **una sola** llamada a
`AskUserQuestion` (máx. 4 preguntas por llamada) al final de la fase, no una por archivo. Ejemplo
de la corrida de agosto 2026: una pregunta por categoría (fotos, riverside, libros, documents),
no 81 preguntas por archivo de `_tmp`.
