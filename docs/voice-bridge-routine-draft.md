# Voice bridge context routine (DRAFT, not installed)

Draft of the scheduled routine that refreshes the voice bridge context file every morning.
Nothing here is active. To install it, copy the block below to
`~/.claude/scheduled-tasks/voice-bridge-context/SKILL.md` in the instance and create the schedule
(suggested: daily 07:30 local time). The owner decides the path and the schedule.

```markdown
---
name: voice-bridge-context
description: Refresca el archivo de contexto que el voice bridge muestra para aprobación. Una corrida diaria; no envía nada, no aprueba nada.
---

Ejecuta una sola vez:

    secretary voice-context compose --out <ruta del archivo configurada en el bridge>

El comando recoge compromisos, briefs pendientes y sesiones activas, y pide a `claude -p` (sin herramientas) elegir y acortar los ítems. Si `claude` falla, escribe los ítems deterministas y lo avisa por stderr.

Primera línea del mensaje final: "ok" si escribió el archivo, "fallback" si usó los ítems deterministas, "error" si no escribió nada. Luego una línea con el recuento por categoría. No edites otros archivos, no abras PR, no envíes correo.
```

The bridge never runs on a schedule by itself: the Refresh button runs the same command by hand, and the
approval step stays in the bridge UI.
