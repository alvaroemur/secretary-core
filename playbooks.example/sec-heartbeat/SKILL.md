---
name: sec-heartbeat
description: Consolidación programada de corto plazo. Escribe latest.md para briefing/pulse.
---

# sec-heartbeat (scheduled task)

Lee contexto en `~/.secretary/CLAUDE.md`, la spec `~/.secretary/_diseño/specs/008-sec-heartbeat/spec.md` y el skill operativo `~/.claude/skills/sec-heartbeat/SKILL.md`.

## Cadencia oficial (Lima)

- 07:10 pre-brief
- q2h: 09:10, 11:10, 13:10, 15:10, 17:10, 19:10, 21:10, 22:10 (10 min después de `reuniones-update` en :00)
- 00:10 close (cierre nocturno; último latido)

Si existe manifiesto central de scheduler (por ejemplo en `.cursor/routines/manifest.yaml`), debe reflejar exactamente esta cadencia.

## Procedimiento runtime (main-only)

El heartbeat es **main-only** — no worktree, no PR. Scheduled y manual usan el mismo flujo.

**Scheduled (launchd):** `~/.secretary/scripts/routines/run-routine.sh sec-heartbeat` → delega a
`~/.claude/scheduled-tasks/sec-heartbeat/run.sh`.

**Manual / sesión interactiva:** invocar el skill operativo (`~/.claude/skills/sec-heartbeat/SKILL.md`)
y al cerrar ejecutar el bloque de cierre abajo (o `run.sh` con `HEARTBEAT_SLOT=session`).

```bash
set -euo pipefail
REPO=~/.secretary
cd "$REPO"
git fetch origin && git pull --rebase origin main
# … generar latest.md + append YYYY-MM-DD.md (solo subsystem/heartbeat/) …
git add subsystem/heartbeat/
git commit -m "chore(heartbeat): latido <slot> $(date +%Y-%m-%d\ %H:%M)"  # omitir si no hay cambios
git push origin main
```

Todas las rutas de escritura cuelgan de `$REPO/subsystem/heartbeat/` (no de un worktree).

## Objetivo

Generar un latido operativo en:
- `$REPO/subsystem/heartbeat/latest.md` (overwrite, verdad actual)
- `$REPO/subsystem/heartbeat/YYYY-MM-DD.md` (append por corrida)

## Inputs mínimos

- `extractors/*/memory/` + `acciones.md`
- `extractors/mail/state.md` (batch ~18:00)
- `subsystem/wip/`
- Issue briefing abierto + comentarios `sec-status`
- Calendario hoy ±1d (`gog calendar`, todas las cuentas registradas)
- Frescura extractoras + conflictos multi-fuente (spec 008 § Frescura / § Conflictos)
  - Script: `$REPO/scripts/routines/extractor-freshness.sh` (precomputado en `run.sh`; copiar verbatim a `## Frescura extractoras`)
- **Git/PR:** `gh pr list` + branch/worktree/dirty scan por repo en allowlist (`.secretary.yml` → `dispatch.executor.repos`) **más** repos Cowork de acc abiertas (`workspace`)

Tabla match: columnas `acc-id | título | repo | ref | estado | evidencia | match | nota` con `match` ∈ `linked | loose-acc | loose-git | —`. Ver doctrina `canon/operational/routines/heartbeat-match-model.md`.

## Reglas de persistencia

1. Escribir `latest.md` con plantilla completa (match acc↔git, delta, huérfanos, pendiente humano).
2. Append en el diario `YYYY-MM-DD.md` bajo `## Latido HH:MM (slot)`.
3. Si faltan fuentes, anotarlo en "Notas operativas" sin inventar estado.

## Cierre (commit + push a main)

```bash
cd "$REPO"
git add subsystem/heartbeat/
git commit -m "chore(heartbeat): latido $(date +%Y-%m-%d\ %H:%M)"
git push origin main
```

- **Tier ambient:** push directo a `main` — sin PR, sin merge posterior, sin babysit del latido.
- Si `git pull --rebase` trae conflicto en `subsystem/heartbeat/`, resolver: `latest.md` = contenido
  del latido recién generado; diario = conservar todos los bloques `## Latido` en orden cronológico.

## Restricciones

- Solo escribir en `subsystem/heartbeat/`.
- No cerrar acciones automáticamente.
- No escribir wiki.
- No enviar mensajes a terceros.
