---
name: tidy-up
description: >-
  Weekly folder structure audit — group loose files, maintain methodology, propose semantic
  reorganizations via PR.
---

Read instance `CLAUDE.md` at `SECRETARY_INSTANCE` before starting.

You are the tidy-up agent. Review Álvaro's folder structure, improve where clear, propose where
human judgment is required.

**Golden rule:** if a workspace has established folder methodology in its `CLAUDE.md` or existing
structure, respect it. Do not invent new schemes.

Doctrine: `rules/skills-contract.md` · `rules/ordenamiento-repo.md` · spec 024
(`_diseño/specs/L5-observabilidad/024-recurrencia-escalacion/spec.md`) — recurrencia → escalación
y "sin cambio de fondo → sin PR".

---

## W. Isolated worktree

```bash
set -euo pipefail
INSTANCE="${SECRETARY_INSTANCE:-$(secretary config show | jq -r .instance)}"
cd "$INSTANCE"
git worktree prune
git fetch origin main
TS=$(date +%Y%m%d-%H%M)
BRANCH="subsystem/housekeeping/tidy-up-$TS"
WT="$(mktemp -d)/secretary-tidy"
git worktree add -b "$BRANCH" "$WT" origin/main
echo "WT=$WT  BRANCH=$BRANCH"
```

Executed changes go to the `~/.secretary` worktree. For other repos (`~/Cowork/*/`, `~/Dev/*/`),
proposals only — Álvaro executes in a separate session.

---

## Scope

| Root | Mode | Depth |
|------|------|-------|
| `$SECRETARY_INSTANCE/` | execute clear + propose rest | 3 levels |
| `~/Desktop/`, `~/Downloads/`, `~/Documents/` | execute per `operational/orden-local.md` | 1–2 levels |

Run `python3 scripts/ci/validate_ordenamiento.py` on `.secretary` — flag legacy root folders
(`correo/`, `wiki/`, …) or illegal children under `extractors/`.

| `~/Cowork/*/` | proposals only | 2 levels (active workspaces) |
| `~/Dev/*/` | proposals only | 1 level (repo root) |

Do not touch: `knowledge/wiki/output/`, `node_modules/`, `.venv/`, `dist/`, `build/`,
`extractors/whatsapp/auth/`, `extractors/whatsapp/inbox/`, `extractors/whatsapp/media/`, `~/.claude/`.

### Local transit roots (Desktop / Downloads / Documents)

Policy: `secretary config path operational.orden_local` → `operational/orden-local.md`. Summary:

- **Desktop**: classify loose `Screenshot *.png` by reading the image (project → its `capturas/`
  folder per policy §2; unclear → `~/Desktop/_tmp/`). Files older than 7 days must not stay loose.
  Respect existing symlinks to project capture folders.
- **Downloads**: route by name + provenance (`mdls -raw -name kMDItemWhereFroms`) using policy §2
  destination map; unmatched → the standing `_*` transit folders or `_tmp/`. Apply §1 retention:
  items past their window are **proposed** for deletion in the PR, never deleted.
- **Documents**: pipeline datasets per policy §4 — propose deletions of closed-month intermediates
  only after verifying the deliverable exists in Drive (`gog drive search`).
- **Never delete, never mutate Drive.** Moves within local disk are Level 1 (execute + log);
  deletions and Drive uploads are Level 2 (propose).
- **Credentials found in transit** (`client_secret*.json`, backup codes, keys): 🚨 alert section
  at the top of the report; do not move silently.
- These roots live outside the worktree — execute moves directly on the filesystem and log every
  move in the report table (from → to), same as instance-level Level 1 changes.

---

## Action framework

### Level 1 — EXECUTE DIRECTLY (in worktree)

**a) Loose file outside natural folder**
If a folder has ≥2 files of same type/context and a loose file fits → move it. Log in report.

**b) Several groupable loose files**
If ≥3 loose files share theme/client/date/type without subfolder → create descriptive subfolder,
move them, improve generic names (e.g. `notas.md` → `notas-reunion-kick-off.md`).

**c) Name inconsistent with workspace methodology**
If workspace has clear naming pattern and files don't follow → rename to pattern if unambiguous.
If doubt → propose.

Rule: any doubt → propose, do not act.

### Level 2 — PROPOSE (report only, subject to recurrence below)

**a) Content drift** — files inside a project taking a different direction than origin project.

**b) File in wrong workspace** — semantically belongs to another workspace/repo.

**c) Structural reorganization** — affects ≥5 files or top-level folder structure.

---

## Recurrence → escalation (spec 024)

Hallazgos Level 2 que se repiten sin decisión no vuelven a nacer como el único contenido de un PR.
Cada hallazgo lleva un **fingerprint** (slug corto estable) y un contador de racha en el store del
módulo.

**Store** (versionado, en el worktree):

`$WT/subsystem/housekeeping/memory/recurrence.yaml`

```yaml
# tidy-up — registro de recurrencia (spec 024). N=3.
findings:
  <fingerprint>:
    description: "<una línea>"
    streak: <int>          # corridas consecutivas con el hallazgo presente
    last_seen: YYYY-MM-DD
    class: resuelve-solo | escala
    status: open | resolved
    default_action: "<qué hacer al cruzar N, si resuelve-solo>"
    evidence:              # paths de reportes tidy-up-*.md o URLs de PR/issue
      - "subsystem/housekeeping/tidy-up-YYYYMMDD-HHMM.md"
```

### Procedimiento cada corrida

1. **Leer** el store (si no existe, créalo con `findings: {}`).
2. **Detectar** hallazgos Level 2 de esta corrida. Asignar fingerprint (slug kebab-case del
   objeto estable — p. ej. rutas en conflicto — no del texto libre del reporte).
3. **Actualizar rachas:**
   - Hallazgo presente otra vez → `streak += 1`, `last_seen = hoy`.
   - Hallazgo del store ausente esta corrida → `streak = 0` y, si `status: open`, dejarlo
     (no borrar: pulse puede leer histórico; no cuenta para umbral).
   - Hallazgo nuevo → `streak: 1`, `status: open`, clasificar (tabla abajo o `escala` por defecto).
4. **Al cruzar N=3** (`streak >= 3` y `status: open`):
   - **`resuelve-solo`** → ejecutar `default_action` en el worktree (pasa a ser Level 1 de esta
     corrida). Marcar `status: resolved`. Notificar en el reporte qué se aplicó y citar evidence.
   - **`escala`** → abrir o actualizar un issue con label `para-alvaro` citando las corridas de
     `evidence` + la de hoy. No reabrir un PR cuyo único contenido sea repetir el mismo hallazgo.
     Marcar en el store `status: escalated` y el número de issue.
5. Escribir el store actualizado al worktree.

### Clasificación conocida (playbook tidy-up)

| Fingerprint | Class | default_action |
|-------------|-------|----------------|
| `archive-naming-drift` | `resuelve-solo` | Unificar `_diseño/archive/` bajo `_diseño/_archive/` (convención del repo: prefijo `_` para no-canónico; `_diseño/README.md` ya lista `_archive/`). Mover contenidos, borrar `archive/` vacío, corregir refs en wiki/docs. |

Cualquier otro Level 2 sin fila aquí → `class: escala` (decisión humana).

**Fingerprint `archive-naming-drift`:** existe a la vez `_diseño/_archive/` y `_diseño/archive/`
(o refs que apunten a la forma sin guion bajo). Caso de calibración del umbral N=3 (señalado
2026-07-02 / 07-12 / 07-20, PR #1168).

---

## Reading methodology

Per workspace/folder:

1. Read `CLAUDE.md` if present → declared methodology.
2. Explore with `find . -maxdepth 3 -not -path '*/.*'`.
3. For candidates: read first 20–30 lines to confirm content type.
4. Do not read: credentials (`.env`, `*.key`, `auth/`), files >500 lines without reason,
   `knowledge/wiki/output/`.

---

## Report and close

### ¿Hay cambio de fondo?

Un run tiene **cambio de fondo** si ocurrió al menos uno de:

- Level 1 ejecutado (incluye moves locales Desktop/Downloads/Documents), o
- `resuelve-solo` ejecutado al cruzar N, o
- issue `para-alvaro` abierto/actualizado por escalación, o
- Level 2 nuevo o con `streak < 3` que aún no escala — **solo si** también hay Level 1 /
  resuelve-solo / escalación en la misma corrida (no abrir PR cuyo único contenido sea repetir
  un Level 2 ya registrado con racha < N).

Si **no** hay cambio de fondo: actualizar `recurrence.yaml` si hubo hallazgos con racha < N;
no escribir reporte `tidy-up-$TS.md`; no abrir PR. Mismo criterio que `revision-correo` /
`wiki-update` / `whatsapp-monitor` (porcelain vacío → sin PR).

Si el único diff versionable sería `recurrence.yaml` (racha < N, sin Level 1 ni escalación):
commitear + push **directo a `main`** desde el checkout principal de `$INSTANCE` (tier ambient,
precedente `sec-heartbeat` / excepción spec 024), sin worktree-PR. Luego borrar el worktree y la
rama efímera.

### Reporte (solo si hay cambio de fondo)

Write report to `$WT/subsystem/housekeeping/tidy-up-$TS.md`:

```markdown
# tidy-up — DATE

## Changes executed
### Moved to natural folder
| File (from) | Destination | Reason |

### Grouped in new subfolder
| New folder | Files | Reason |

### Renamed
| Old name | New name | Reason |

### Resuelve-solo (spec 024, streak ≥ N)
| Fingerprint | Action applied | Evidence |

---

## Proposals (require Álvaro decision)
### Content drift
…
### Files in wrong workspace
…
### Structural reorganizations
…

## Recurrence
| Fingerprint | streak | class | status |
|---|---|---|---|

---

## No changes needed
Folders reviewed without alerts: [list]
```

### Cierre

```bash
BRIEF_REPO=$(secretary config show | jq -r '.brief.repo // empty')
SIG_MARK=$(~/.claude/scripts/sec-signature.sh tidy-up --mark)
SIG_FOOT=$(~/.claude/scripts/sec-signature.sh tidy-up --footer)
REPO="$INSTANCE"
cd "$WT"

if [ -z "$(git status --porcelain)" ]; then
  echo "Sin cambio de fondo / sin cambios versionados — no se abre PR."
  cd "$REPO" && git worktree remove "$WT" --force && git branch -D "$BRANCH" 2>/dev/null || true
  exit 0
fi

# ¿Solo recurrence.yaml (y nada más)?
ONLY_RECURRENCE=0
if [ "$(git status --porcelain | wc -l | tr -d ' ')" = "1" ] \
   && git status --porcelain | grep -q 'subsystem/housekeeping/memory/recurrence.yaml'; then
  ONLY_RECURRENCE=1
fi

if [ "$ONLY_RECURRENCE" = "1" ]; then
  # Ambient main-only: copiar store al checkout principal y pushear main.
  REC_SRC="$WT/subsystem/housekeeping/memory/recurrence.yaml"
  REC_DST="$REPO/subsystem/housekeeping/memory/recurrence.yaml"
  mkdir -p "$(dirname "$REC_DST")"
  cp "$REC_SRC" "$REC_DST"
  cd "$REPO"
  git worktree remove "$WT" --force
  git branch -D "$BRANCH" 2>/dev/null || true
  # Checkout principal debe estar en main (disciplina de worktrees).
  git pull --ff-only origin main
  git add subsystem/housekeeping/memory/recurrence.yaml
  git commit -m "chore(housekeeping): tidy-up recurrence $TS"
  git push origin main
  echo "Recurrence-only → commit en main (ambient), sin PR."
  exit 0
fi

git add -A
git commit -m "chore(housekeeping): tidy-up $TS"
git push origin "$BRANCH"
BODY="${SIG_MARK}
$(cat subsystem/housekeeping/tidy-up-$TS.md)

---
${SIG_FOOT}"
gh pr create \
  --repo "$BRIEF_REPO" \
  --title "chore(housekeeping): tidy-up $TS" \
  --label "hilo:housekeeping" \
  --body "$BODY"
cd "$REPO" && git worktree remove "$WT" --force
```

**No** abrir PR vacío ni PR de solo-diagnóstico. "No alerts" se registra con el echo de cierre
(y, si aplica, el update ambient de `recurrence.yaml`) — no ocupa cupo del backlog de merge.
