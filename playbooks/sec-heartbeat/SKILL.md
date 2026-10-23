---
name: desk-heartbeat
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

## Delegación a Haiku (piloto D15.8)

Si el runtime no ofrece subagentes con `model`, la sesión principal hace ambas operaciones y lo anota como "no delegada" en "Notas operativas".

**1. Inventario git/PR por repo**

- **Operación:** `gh pr list` + rama/worktrees/dirty de cada repo de la allowlist y de los repos Cowork de acc abiertas.
- **Entrada mínima:** la lista de repos (`{repo, path}`) y los comandos a correr. Sin este playbook ni acciones.
- **Llamada:** `subagent_type: general-purpose`, `model: "haiku"`.
- **Salida estricta (JSON):** `[{"repo": "…", "rama": "…", "worktrees": ["…"], "dirty": n, "prs": [{"number": n, "headRefName": "…", "title": "…", "body_acc_ids": ["acc-…"]}]}]`.
- **Validación:** filas = repos de entrada; spot-check de 1 repo al azar reejecutando sus comandos.
- **Fallback:** si falla, la sesión principal hace el inventario una vez y lo anota en "Notas operativas".

**2. Tabla de correspondencia acc ↔ git**

- **Operación:** armar la tabla match de arriba a partir del inventario validado.
- **Entrada mínima:** acc abiertas como `{acc_id, titulo, workspace}` y el JSON del inventario validado.
- **Llamada:** `subagent_type: general-purpose`, `model: "haiku"`.
- **Salida estricta:** la tabla match en Markdown con las columnas de arriba.
- **Validación:** cada acc-id de entrada aparece exactamente una vez; cada fila `linked` tiene el acc-id literal en el nombre de rama o en el body del PR citado (comprobado contra el inventario). Las filas que no cumplen bajan a `loose-acc`/`loose-git`.
- **Fallback:** si falla, la sesión principal arma la tabla una vez y lo anota.

Ninguna operación delegada escribe en `subsystem/heartbeat/`, cierra acciones ni hace commit. El latido incluye en "Notas operativas" una línea por operación delegada con su resultado de validación.

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


## Visibilidad de decisiones pendientes · Desk

Lee `desk-context/references/control.md` instalado. Antes de terminar, distingue una corrida vacía de una rutina que ya no puede aportar valor. Si faltan fuentes/accesos, se agota la cola o se necesita cambiar estrategia fuera de una regla ya aprobada: busca issues `desk:decision`/`para-alvaro` del mismo problema y actualiza el canónico o crea uno firmado. Incluye rutina/proyecto, fingerprint estable, evidencia fechada, consecuencia de esperar, opciones, recomendación y decisión requerida. No lo dejes solo en state, log o PR ni crees un duplicado diario. Revisa decisiones anteriores antes de volver a pedirlas. Si puedes resolverlo bajo una regla vigente, resuélvelo y reporta el resultado, sin inventar otra compuerta. No amplía tus permisos de envío, fuentes o negocio. Brief y overview consumirán esta misma decisión.


## Visibilidad de decisiones pendientes · Desk

Lee `desk-context/references/control.md` instalado. Antes de terminar, distingue una corrida vacía de una rutina que ya no puede aportar valor. Si faltan fuentes/accesos, se agota la cola o se necesita cambiar estrategia fuera de una regla ya aprobada: busca issues `desk:decision`/`para-alvaro` del mismo problema y actualiza el canónico o crea uno firmado. Incluye rutina/proyecto, fingerprint estable, evidencia fechada, consecuencia de esperar, opciones, recomendación y decisión requerida. No lo dejes solo en state, log o PR ni crees un duplicado diario. Revisa decisiones anteriores antes de volver a pedirlas. Si puedes resolverlo bajo una regla vigente, resuélvelo y reporta el resultado, sin inventar otra compuerta. No amplía tus permisos de envío, fuentes o negocio. Brief y overview consumirán esta misma decisión.
