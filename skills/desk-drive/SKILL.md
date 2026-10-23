---
name: desk-drive
description: >-
  Read fresh Drive state — file index, drive-crawler's unmerged organization
  proposals, and drive-sync mirror drift — before answering "what's in Drive"
  or acting on a Doc/Sheet. Delegates writes to drive-sync (mirrors) or
  drive-crawler (index proposals); never moves/deletes/renames in Drive itself.
  Triggers: "/desk-drive", "qué hay en Drive de…", "organiza el Drive",
  "busca en Drive", "propuestas del crawler".
---

# desk-drive — Drive fresh-first (index + mirrors)

**What this does:** close the gap between "file landed in Drive" and "wiki/session knows about
it" — probe live Drive, read `drive-crawler`'s unmerged proposals, and check `drive-sync`
mirror drift. **Never mutates Drive directly** (no move/rename/delete); that's either
`drive-crawler`'s proposal (human-approved in PR) or `drive-sync`'s manifest-driven sync.

Doctrine: `rules/skills-contract.md` · `rules/extractor-ops.md` § desk-drive

## Instance setup

```bash
eval "$(secretary env)"
CFG=$(secretary config show)
PERSONAL_ACCOUNT=$(echo "$CFG" | jq -r '.accounts.personal // empty')
```

## Two paths (do not conflate)

| Path | Skill / routine | Writes |
|------|------------------|--------|
| **Index + organization** (root clutter, "what's in Drive", proposed moves) | `drive-crawler` (batch routine) | Only proposals in PR `drive/auto-*` — session never moves/deletes |
| **Docs/Sheets mirrored locally** (edit a Doc, sync a Sheet) | `drive-sync` skill | `cowork sync fetch/sync` with `.drivesync.yaml` manifest |

If the ask is "edit/update this Doc or Sheet" → stop here, delegate to `drive-sync` skill directly (do not duplicate its fetch/sync protocol).

If the ask is "what's in Drive", "find X", "any new files", "did the crawler propose anything" → continue below.

If the ask is "share this file with X" / "give access to Y" → see "## Compartir permisos" below —
distinct from both paths above, not organization and not content sync.

## Inputs

| Field | Values |
|-------|--------|
| `intent` | `search` (default) \| `probe` \| `proposals` \| `recall` |
| `query` | Drive search term or file name fragment |
| `folder_id` | Optional — scope to a known parent folder |

## Loop fresh-first

### Step 0 — Fresh (required)

```bash
secretary fresh drive --format json
# main: extractors/drive/state.md + last merge; auto_pr: open drive/auto-* PRs; fuente_viva: live probe
```

Read unmerged proposals (if `auto_pr` non-empty):

```bash
gh pr list --repo "$(secretary config get brief.repo)" --state open --json number,headRefName,title \
  | jq '[.[] | select(.headRefName | startswith("drive/auto-"))]'
git -C "$SECRETARY_INSTANCE" show origin/<branch>:extractors/drive/organization.md | tail -80
```

### Step 0b — Live probe (query/search intents)

```bash
gog drive search "name contains 'término'" --account="$PERSONAL_ACCOUNT" --max 10 --plain --no-input
gog drive get <fileId> --json --account="$PERSONAL_ACCOUNT" --no-input
gog drive ls --parent=<folderId> --json --account="$PERSONAL_ACCOUNT" --no-input
```

Cross-check against local mirrors before assuming a file is unorganized: `extractors/drive/organization.md` (cumulative proposals log), `extractors/drive/memory/`.

### Step 1 — Recall

`desk-recall` on the file/topic/org — wiki may already have a pointer (`entidades.md` with Drive link) even if the crawler hasn't proposed a move yet.

### Step 2 — Action

Session **does not** move, rename, or delete Drive files. Options:

1. Report current organization state + open crawler proposals (if any).
2. If owner wants a Doc/Sheet **edited** → hand off to `drive-sync` skill (fetch → plan → apply).
3. If owner wants root clutter organized → point to `drive-crawler` next scheduled run, or offer to trigger it.
4. After crawler PR exists → offer `babysit` to keep it merge-ready; merge decision is the owner's.

## Compartir permisos (`gog drive share`)

`gog drive share <fileId> --email=X --role=reader|writer` (unshare: `gog drive unshare <fileId>
<permissionId>`) es una categoría de mutación distinta de "never mutates Drive" (esa regla cubre
mover/renombrar/eliminar — reorganización; compartir es otorgar acceso persistente, no reorganizar
un archivo).

Puede correrse desde una sesión, **nunca sin confirmación explícita separada** — mostrar a Álvaro
qué archivo, qué destinatario/email, qué rol, antes de ejecutar. Default `role=reader` salvo que el
caso pida `writer` explícitamente. Esta confirmación es adicional a cualquier gate de envío de
correo que la acompañe — son dos decisiones distintas aunque vengan juntas (ver
`secretary-briefing/SKILL.md` § Phase 2.7 "Automatismos de catálogo", rama `tipo: persona`, acción
`compartir-transcripcion`).

Cuando la propuesta de compartir viene de un issue `secretary:proponer` abierto por
`secretary-briefing`, quien trabaja el issue (sesión humana — este label no lo reclama
`dispatch-executor`) ejecuta el `share` tras confirmar.

`gog drive permissions <fileId>` (solo lectura, lista permisos existentes) sigue siendo apropiado
sin gate — es la misma naturaleza de lectura que el resto de este skill.

## Guardrails

- **NEVER** move/rename/delete via `gog drive` from this skill without the owner's proposal path (`drive-crawler`). Compartir permisos (`gog drive share`) es otra categoría — ver arriba, siempre con confirmación explícita separada, nunca bloqueado por esta regla.
- Loose root files are typically upload residue → default proposal is delete, not move (see `feedback_drive_residuos_root.md`).
- Docs/Sheets with `protect_styling: true` in a `.drivesync.yaml` manifest → never raw-push markdown; that's `drive-sync`'s guardrail, not this skill's to override.

## Integration

| Skill / routine | Role |
|------------------|------|
| `desk-recall` | Step 1; delegates Paso 0 here for "what's in Drive" questions |
| `drive-crawler` | Batch index + organization proposals (PR `drive/auto-*`); sole source of move/delete proposals |
| `drive-sync` | Manifest-driven Doc/Sheet mirror sync; this skill hands off, doesn't duplicate |
| `secretary fresh drive` | Atomic step 0 (main, auto-pr, live probe) |
| `secretary-briefing` (Phase 2.7, automatismos de catálogo) | Originates `share` proposals via `secretary:proponer` issue (not `delegate:execute` — this isn't repo/PR work, see that phase's doctrine) — this skill's doctrine is what the issue-worker follows to execute them |

Doctrine: `rules/extractor-ops.md` · Spec: `_diseño/specs/L3-captura/010-extractor-skills/spec.md` § desk-drive
