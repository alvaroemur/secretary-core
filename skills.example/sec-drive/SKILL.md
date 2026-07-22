---
name: sec-drive
description: >-
  Read fresh Drive state — file index, drive-crawler's unmerged organization
  proposals, and drive-sync mirror drift — before answering "what's in Drive"
  or acting on a Doc/Sheet. Delegates writes to drive-sync (mirrors) or
  drive-crawler (index proposals); never moves/deletes/renames in Drive itself.
  Triggers: "/sec-drive", "qué hay en Drive de…", "organiza el Drive",
  "busca en Drive", "propuestas del crawler".
---

# sec-drive — Drive fresh-first (index + mirrors)

**Mission:** close the gap between "file landed in Drive" and "wiki/session knows about
it" — probe live Drive, read `drive-crawler`'s unmerged proposals, and check `drive-sync`
mirror drift. **Never mutates Drive directly** (no move/rename/delete); that's either
`drive-crawler`'s proposal (human-approved in PR) or `drive-sync`'s manifest-driven sync.

Doctrine: `rules/skills-contract.md` · `rules/extractor-ops.md` § sec-drive

## Instance setup

```bash
CFG=$(secretary config show)
export SECRETARY_INSTANCE="${SECRETARY_INSTANCE:-$(echo "$CFG" | jq -r .instance)}"
PERSONAL_ACCOUNT=$(echo "$CFG" | jq -r '.accounts.personal // empty')
```

## Two paths (do not conflate)

| Path | Skill / routine | Writes |
|------|------------------|--------|
| **Index + organization** (root clutter, "what's in Drive", proposed moves) | `drive-crawler` (batch routine) | Only proposals in PR `drive/auto-*` — session never moves/deletes |
| **Docs/Sheets mirrored locally** (edit a Doc, sync a Sheet) | `drive-sync` skill | `cowork sync fetch/sync` with `.drivesync.yaml` manifest |

If the ask is "edit/update this Doc or Sheet" → stop here, delegate to `drive-sync` skill directly (do not duplicate its fetch/sync protocol).

If the ask is "what's in Drive", "find X", "any new files", "did the crawler propose anything" → continue below.

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
gh pr list --repo yourusername/cowork-secretary --state open --json number,headRefName,title \
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

`sec-recall` on the file/topic/org — wiki may already have a pointer (`entidades.md` with Drive link) even if the crawler hasn't proposed a move yet.

### Step 2 — Action

Session **does not** move, rename, or delete Drive files. Options:

1. Report current organization state + open crawler proposals (if any).
2. If owner wants a Doc/Sheet **edited** → hand off to `drive-sync` skill (fetch → plan → apply).
3. If owner wants root clutter organized → point to `drive-crawler` next scheduled run, or offer to trigger it.
4. After crawler PR exists → offer `babysit` to keep it merge-ready; merge decision is the owner's.

## Guardrails

- **NEVER** move/rename/delete via `gog drive` from this skill. Organization is `drive-crawler`'s proposal, applied by the owner.
- Loose root files are typically upload residue → default proposal is delete, not move (see `feedback_drive_residuos_root.md`).
- Docs/Sheets with `protect_styling: true` in a `.drivesync.yaml` manifest → never raw-push markdown; that's `drive-sync`'s guardrail, not this skill's to override.

## Integration

| Skill / routine | Role |
|------------------|------|
| `sec-recall` | Step 1; delegates Paso 0 here for "what's in Drive" questions |
| `drive-crawler` | Batch index + organization proposals (PR `drive/auto-*`); sole source of move/delete proposals |
| `drive-sync` | Manifest-driven Doc/Sheet mirror sync; this skill hands off, doesn't duplicate |
| `secretary fresh drive` | Atomic step 0 (main, auto-pr, live probe) |

Doctrine: `rules/extractor-ops.md` · Spec: `_diseño/specs/L3-captura/010-extractor-skills/spec.md` § sec-drive
