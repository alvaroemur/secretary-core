# Firma en artefactos GitHub (rutinas Secretary)

Toda rutina que entrega PR, issue o comentario debe usar **`~/.claude/scripts/sec-signature.sh`**
— no hardcodear autor ni marca.

Doctrina canónica (instance): `rules/github-signatures.md` en `~/.secretary`.

## Generar

```bash
# Rutinas: invoke-*.sh exportan SECRETARY_RUN_ID, SECRETARY_SIGNATURE_CONTEXT, SECRETARY_MODEL, SECRETARY_BRANCH
SIG_MARK=$(~/.claude/scripts/sec-signature.sh <contexto> --mark)
SIG_FOOT=$(~/.claude/scripts/sec-signature.sh <contexto> --footer)
```

Sesión interactiva (skills wind-down, dispatch, …):

```bash
export SECRETARY_SKILL=wind-down   # o dispatch, sec-dream, sesion, …
export SECRETARY_BRANCH=$(git branch --show-current 2>/dev/null || true)
SIG_MARK=$(~/.claude/scripts/sec-signature.sh "${SECRETARY_SKILL}" --mark)
SIG_FOOT=$(~/.claude/scripts/sec-signature.sh "${SECRETARY_SKILL}" --footer)
```

`<contexto>` = id de la rutina (`housekeeping`, `revision-correo`, `wiki-update`, …) o skill en sesión.

## Colocar

| Artefacto | Marca oculta | Footer visible |
|-----------|--------------|----------------|
| Body de PR / issue | **Primera línea** | Tras `---`, **última línea** |
| Comentario en PR/issue | Primera línea del comentario | Opcional al final si es largo |

## Qué produce

**Marca** (filtro máquina, una línea HTML) — solo incluye pares `key=value` cuando el valor está definido:

```html
<!-- agent-generated:<contexto> runtime=<cursor|claude-code|sesion|api> run=<id> branch=<slug> model=<slug> ref=<short> -->
```

**Footer** (humano, una línea):

```text
🤖 _<Autor> · <contexto>[ → branch][ · model][ · run <short>] · YYYY-MM-DD_
```

Ejemplo rutina enriquecida:

```text
<!-- agent-generated:housekeeping runtime=cursor run=housekeeping-2026-07-08-014400 branch=housekeeping/tidy model=auto -->
🤖 _Cursor · housekeeping → housekeeping/tidy · run 014400 · 2026-07-08_
```

Excepción: `secretary-briefing` usa autor `Secretary` y contexto `briefing` (marca el producto).

## Variables de entorno

| Variable | Uso |
|----------|-----|
| `SECRETARY_SIGNATURE_CONTEXT` | Contexto (rutinas: `invoke-*.sh` lo fija al `routine_id`) |
| `SECRETARY_SKILL` | Alias de contexto en skills interactivos |
| `SECRETARY_RUN_ID` | Id de corrida (`<routine>-<fecha>-<HHMMSS>`) |
| `SECRETARY_MODEL` / `SECRETARY_AGENT_MODEL` | Modelo del agente |
| `SECRETARY_BRANCH` | Rama git (slug); si falta, se infiere de `git branch --show-current` |
| `SECRETARY_AGENT_REF` | Ref corta opcional (task id, chip, …) |
| `SECRETARY_RUNTIME` | Fuerza `runtime=` (`cursor`, `claude-code`, `api`, `sesion`) |
| `SECRETARY_SIGNATURE_DATE` | Fecha en footer (tests) |

Jerarquía de contexto en la marca: **skill/contexto → branch → model → run_id → agent ref**.

## Runtime

| Origen | `runtime=` | Autor visible |
|--------|------------|---------------|
| Cursor Automation / `run-routine.sh` (cursor-cron) | `cursor` | Cursor |
| Claude Code scheduled task | `claude-code` | Claude Code |
| Sesión interactiva Claude | `sesion` | Claude Code |
| API cron (`invoke-api.sh`) | `api` | API cron |

`run-routine.sh` + `read-routine-config.sh` exportan `SECRETARY_RUNTIME`. Los invoke scripts exportan
`SECRETARY_RUN_ID`, `SECRETARY_SIGNATURE_CONTEXT` y `SECRETARY_MODEL` antes de lanzar el agente.

## Filtrar comentarios de agente (no son feedback humano)

Excluir si el body contiene:

- `<!-- agent-generated:` o legacy `<!-- claude-generated:`
- Footer `🤖 _` con patrón de firma (p. ej. `· run `, `→`, `Secretary — briefing`)

Legacy `<!-- claude-generated:... -->` sigue siendo señal de agente al filtrar — ver docs, no generar nuevas.

Doctrina global: `~/.claude/CLAUDE.md` §Firma en comentarios y textos generados.
