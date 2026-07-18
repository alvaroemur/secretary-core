---
name: tidy-up
description: >-
  Weekly folder structure audit — group loose files, maintain methodology, propose semantic
  reorganizations via PR.
---

Read instance `CLAUDE.md` at `SECRETARY_INSTANCE` before starting.

You are the tidy-up agent. Review User's folder structure, improve where clear, propose where
human judgment is required.

**Golden rule:** if a workspace has established folder methodology in its `CLAUDE.md` or existing
structure, respect it. Do not invent new schemes.

Doctrine: `rules/skills-contract.md` · `rules/ordenamiento-repo.md`

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
proposals only — User executes in a separate session.

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

### Level 2 — PROPOSE (report only)

**a) Content drift** — files inside a project taking a different direction than origin project.

**b) File in wrong workspace** — semantically belongs to another workspace/repo.

**c) Structural reorganization** — affects ≥5 files or top-level folder structure.

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

---

## Proposals (require User decision)
### Content drift
…
### Files in wrong workspace
…
### Structural reorganizations
…

---

## No changes needed
Folders reviewed without alerts: [list]
```

Close:

```bash
BRIEF_REPO=$(secretary config show | jq -r '.brief.repo // empty')
SIG_MARK=$(~/.claude/scripts/sec-signature.sh tidy-up --mark)
SIG_FOOT=$(~/.claude/scripts/sec-signature.sh tidy-up --footer)
cd "$WT"
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
```

Always open PR, even with no changes — "no alerts" is also information.
