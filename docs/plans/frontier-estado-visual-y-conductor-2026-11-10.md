---
id: frontier-estado-visual-y-conductor
goal: Tener en cualquier repo una vista de estado casi en tiempo real (planes, sesiones, worktrees, PR) con poco contexto, y un meta-skill «conductor» que encadene frontier, topology y delegate para no dejar al propietario colgado
status: draft
created: 2026-11-10
---

# Frontier: estado visual y conductor (10-nov-2026)

Estado: borrador, ronda 1. Sin aprobación de ejecución. No cambia código. Su casa natural es `secretary-core` (ahí vive `desk-overview`), no en el repo donde se originó el borrador; este archivo es solo el registro provisional.

## Alcance
- Entra: (1) capa de estado visual y en vivo por repo; (2) meta-skill conductor que lee ese estado, relaciona la sesión actual con el backlog y propone el siguiente paso.
- Sale: construir cualquiera de los dos antes de confirmar; cambios en el repo de origen del borrador.

## Requisitos del propietario (palabras suyas, resumidas)
- Ver siempre: qué planes están en marcha, en qué sesiones ha trabajado, dónde está parado; más en tiempo real que `desk-overview`.
- Economizar contexto: nada que escriba mucho en el chat; no preguntar qué es X, Y, Z (A1, T0, V2) ni cómo se relacionan con worktrees, PR, issues, arneses.
- Abrible siempre: desde una sesión o como web de secretary, con la que se pueda hablar, extendida al estado de los repos.
- Conductor: usa frontier, topology, desk-project, etc.; lleva el control; en una sesión puntual (tema Mx) avisa «Mx se relaciona con M del backlog; terminemos eso y luego N, P y Q».

## Hechos verificados (fuente)
- `desk-overview` tiene 131 líneas de instrucciones y vuelca el resultado al chat (`secretary-core/skills/desk-overview/SKILL.md`). `desk-state` lee notas WIP y no comprueba sesiones en vivo.
- `kanban-code` (Apache 2.0) une sesión, worktree, rama y PR por ID de sesión, rama y ruta; usa hooks de Claude Code y `~/.claude/projects`; tiene CLI con `--json`; solo Claude Code; app nativa (macOS 26 o Windows), sin web documentada.
- Patrón repetido en monitores web: hooks que envían a un servidor local y de ahí al navegador, con un vigilante de transcripciones como respaldo (`ccmon`, `vigie`).
- `agent-console` lee transcripciones de Codex y de Claude Code. Ninguna herramienta revisada lee `docs/plans` ni muestra nodos de plan. Fuentes: búsquedas web del 10-nov, sin abrir todos los repos.

- Herramientas que poseen la sesión: `agent-of-empires` (MIT; tmux por agente; 8 arneses incl. Claude Code, Codex, Gemini, Copilot; web con `aoe serve`; CLI y API HTTP; no se sabe si observa sesiones lanzadas por otras apps), `herdr` (Apache-2.0; posee las terminales; Claude Code, Codex, Cursor, OpenCode, Grok; CLI y socket; sin web ni JSON documentados), `Nimbalyst` (MIT; Electron; Claude Code y Codex; worktree por sesión; tareas y planes como Markdown en el repo; SDK de extensiones y MCP), `vibe-kanban` (Apache-2.0; anuncia cierre; base de datos propia). Fuente: READMEs abiertos el 10-nov; ninguna se instaló ni se probó.
- Observadores: `kanban-code` (solo Claude Code, reconcilia sesión, worktree, rama y PR; CLI con JSON); `agent-console` (lee transcripciones de Claude Code y Codex); `ccmon`, `vigie` (hooks hacia servidor local y navegador).
- Las sesiones del propietario nacen en la app de escritorio de Claude (worktrees en `.claude/worktrees`) y en Codex, no en tmux; la política global manda `.wt/<rama>`. El conductor debe tolerar ambas rutas.

## Decisiones aceptadas
- CND-1 skill delgada `conductor` en `secretary-core`. CND-2 habla solo en tres momentos (abrir, relación detectada, cerrar), una o dos líneas. CND-3 la fuente de verdad son los planes del repo más la capa de estado, y el conductor ayuda a mantener la disciplina de secretary. CND-4 lee y propone; escribe en el plan solo con OK; no lanza, mergea ni archiva sin OK salvo reglas permanentes; debe poder llevar sesiones en varios arneses y saltar de una a otra como dispatch. CND-5 versión mínima del conductor ya, leyendo lo que existe, y luego cambiar la fuente por la capa de estado.
- Condiciones del propietario: sirve a todos los arneses; compatible con la visibilidad de planes; el trabajo se hace en `secretary-core` con una sesión nueva que evalúa herramientas.

## Log
- Ronda 12, respuestas: CND-1 a CND-5 OK con las condiciones de arriba.
- Ronda 13 (propuesta): HRN-1, HRN-2, PLN-1, DIS-1, SAL-1, SUP-1, EVL-1.
- Hallazgo (máquina del propietario, 10-nov): los tres arneses dejan transcripciones locales legibles: Claude Code en `~/.claude/projects/**/*.jsonl` (88 archivos modificados en las últimas 24 h), Codex en `~/.codex/sessions/AAAA/...` (4 en 2 días) y Cursor en `~/.cursor/projects/<espacio>/agent-transcripts`. Un adaptador por transcripciones sirve a los tres sin hooks. `~/.claude/settings.json` ya tiene hooks de 10 eventos (Notification, PermissionRequest, PostToolUse, PreToolUse, SessionEnd, SessionStart, Stop, StopFailure, SubagentStop, UserPromptSubmit): agregar otros exige no pisarlos.
- Ronda 13, respuestas: HRN-1 adaptadores, pero con vista HTML en vivo como requisito; HRN-2 Claude Code, Codex y Cursor (uso indistinto); PLN-1 sí (frontmatter `id`, `goal`, `status` y nodos `nX` con `session`, `harness`, `branch`, `pr`); DIS-1 sí (todo en modo «avisa»); SAL-1 sí (relevo estructurado de 4 KB, `.briefs`, bloque pegable por arnés); SUP-1 OK (núcleo con CLI `--json` primero; la vista HTML en vivo entra en la v0 sobre ese núcleo); EVL-1 ok con los requisitos dichos (multi-arnés, ve las sesiones de la app de escritorio, lee planes, no crea worktrees, licencia, mantenimiento, costo de contexto).
- Ronda 14 (propuesta): HTM-1, PRV-1, CHT-1.
- Ronda 14, respuestas: HTM-1 (a) HTML en vivo solo local, en un puerto accesible únicamente desde el Mac (el acceso externo se decide aparte); PRV-1 (a) solo metadatos (título, arnés, repo, rama, worktree, PR, estado, hora, plan y nodo), sin contenido de transcripciones; CHT-1 el chat con el estado va después de la v0. Frontera vacía. Estado: resumen final pendiente de «confirmo»; sin ejecución aprobada hasta entonces.
