# conductor — relevo entre arneses (Claude Code, Codex, Cursor)

Se usa al cambiar de sesión o de arnés. Tope **4 KB** para el handoff completo; si no
cabe, recorta detalle, nunca el bloque pegable. Solo metadatos y decisiones: sin
contenido de transcripciones, credenciales ni datos privados. Un solo archivo en
`.briefs/YYYY-MM-DD-HHMM-<slug>.md` (reusa el brief vigente si existe; con `handover`
activo, delega en él). Escribir el brief requiere OK.

## Estructura del handoff

```
plan: <id> · nodo: <nX · título>   rama: <rama>   worktree: <ruta>   PR: <#n o ninguno>
Hecho: <≤3 viñetas>
Decidido: <≤3 viñetas, con quién decidió>
Pendiente: <≤3 viñetas, la primera es el siguiente paso>
Bloqueos: <o "ninguno">
Verifica primero: <comando que confirma si el trabajo ya está hecho>
```

## Bloque pegable (uno por arnés destino)

Un bloque `text` que empieza por «Verifica si ya está hecho: <comando>». Luego el
handoff pegado. Ajustes por destino:

- **Claude Code:** indica abrir en el worktree; el skill `conductor` se invoca con `/conductor`.
- **Codex:** pide leer `AGENTS.md` y el brief; no asume skills de Claude.
- **Cursor:** apunta a `.briefs/<archivo>` y a `.cursorrules`.

El conductor propone el bloque; no lanza la sesión. Para lanzarla usa `jump`/`delegate`
con OK.
