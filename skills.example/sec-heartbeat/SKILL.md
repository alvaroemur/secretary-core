---
name: sec-heartbeat
description: Consolidate short-term memory into subsystem/heartbeat/ — scheduled + invocable in session. Pulse reads; heartbeat writes.
---

# sec-heartbeat

Consolidates environment signals into **`subsystem/heartbeat/`** (`latest.md` + daily log). Split from `pulse`:
- `pulse` **reads**.
- `sec-heartbeat` **writes**.

## Triggers

- Scheduled: `reuniones-update` **:00** → `sec-heartbeat` **:10** (pre-brief, q2h, close slots — see instance routine manifest).
  Runtime: `$SECRETARY_INSTANCE/scripts/routines/run-routine.sh sec-heartbeat` → harness scheduled-task `run.sh`.
- Session: "heartbeat", "what changed in the environment", "consolidate short-term", "update pulse".
- Chained: after material changes in `wind-down` and `sec-merge`.

## Write store (only destination)

```
$SECRETARY_INSTANCE/subsystem/heartbeat/latest.md
$SECRETARY_INSTANCE/subsystem/heartbeat/YYYY-MM-DD.md
```

Hard rule: do not write outside `subsystem/heartbeat/`.

Resolve paths:

```bash
CFG=$(secretary config show)
INSTANCE="${SECRETARY_INSTANCE:-$(echo "$CFG" | jq -r .instance)}"
HEARTBEAT_DIR=$(secretary config path operations.heartbeat)
TIMEZONE=$(echo "$CFG" | jq -r '.timezone // "UTC"')
```

## Mandatory ingest sources

1. `extractors/*/memory/` and `acciones.md` (open / in-progress acc-ids).
2. `extractors/mail/state.md` (evening batch; may lag on morning runs).
3. `subsystem/wip/`.
4. Open brief (`brief.label` from config) + `sec-status` comments (**priority over acciones.md** for state).
5. **Calendar** (read-only) — events today ±1 day:
   ```bash
   TZ="$TIMEZONE"
   FROM=$(date -v-1d +%Y-%m-%d 2>/dev/null || date -d 'yesterday' +%Y-%m-%d)
   TO=$(date -v+2d +%Y-%m-%d 2>/dev/null || date -d '+2 days' +%Y-%m-%d)
   PERSONAL=$(echo "$CFG" | jq -r '.accounts.personal // empty')
   WORK=$(echo "$CFG" | jq -r '.accounts.Company // .accounts.work // empty')
   [ -n "$PERSONAL" ] && gog calendar events --account="$PERSONAL" --from "$FROM" --to "$TO" --plain
   # Repeat per work account if registered in gog
   ```
6. **Freshness** — run `$INSTANCE/scripts/routines/extractor-freshness.sh` and include output verbatim in `## Extractor freshness`.
7. **Git/PR per repo** — systematic sweep:
   - Allowlist: `dispatch.executor.repos` from config (each `owner/repo` + local `path`).
   - Plus Cowork repos referenced by open actions (`workspace` field in acciones.md).
   - Per repo: `gh pr list`, `git worktree list`, `git branch -vv`, `git status -sb`.
   - Cross-match acc-ids against PR titles, branch names, dirty trees.

8. **Multi-source conflicts** — if `extractors/mail/state.md` contradicts a recent `summaries/` entry or calendar on the same entity, flag in Operational notes citing both sources. Do not invent resolution.

If a source fails, record the gap in Operational notes; do not fabricate data.

## Output format (`latest.md`)

Fixed structure for briefing/pulse consumption:

```markdown
# Heartbeat
- timestamp: YYYY-MM-DD HH:MM (<timezone from config>)
- slot: pre-brief | q2h | close | session
- source: scheduled | interactive

## Match acc↔git
| acc-id | title | repo | ref | state | evidence | match | note |
|---|---|---|---|---|---|---|---|
| acc-... | <action from acciones.md, ~80 chars> | cowork-sideproject | PR #N open | 🔄 in-progress | extractors/meetings/memory/acciones.md + gh pr view | 🔗 linked | ... |
| acc-... | <action> | cowork-sideproject | — | ○ open | extractors/meetings/memory/acciones.md | 📋 loose-acc | no branch/PR |
| — | <PR title> | secretary-core | PR #N open | — | gh pr list (secretary-core) | 🌿 loose-git | no acc-id |

**Legend:** match — 🔗 linked · 📋 loose-acc · 🌿 loose-git · · informational · state — ○ open · 🔄 in-progress · ✅ done · ⏳ stale

Doctrine: `canon/operational/routines/heartbeat-match-model.md`

### Title rule
- **acc-*:** grep `acc-id` in `extractors/*/memory/acciones.md` → `accion:` field. Truncate ~80 chars.
- **loose-git:** PR title (`gh pr view --json title`).
- **informational:** short human-readable description.

### Evidence rule (paths)
- **acc-id:** full path to acciones file — never bare `acciones.md`.
- **update/summary:** `extractors/meetings/summaries/….md`.
- **brief:** `brief #N (issue)`.
- **gh:** `gh pr list (<repo-slug>)` or `gh pr view (<owner/repo>#N)`.
- Combine with ` + ` when needed.

## Delta vs previous beat
- New:
- Closed:
- State changes:

## Orphans
- loose-acc (N): [acc-ids without ref]
- loose-git (N): [PRs/branches without acc-id]
- top actionables: [1–3 most urgent loose items]

## Extractor freshness

**Mandatory section.** In scheduled runs, `run.sh` precomputes via `extractor-freshness.sh` — **copy verbatim** into `latest.md` and the daily append (do not paraphrase unless correcting a factual error with a note in Operational notes).

In interactive session (without `run.sh`): after writing `latest.md`, run
`$INSTANCE/scripts/routines/inject-heartbeat-freshness.sh`.

## Pending human
- blocking decision/send/confirmation:

## Operational notes
- read errors, down sources, evidence limits:
- multi-source conflicts (mail vs meetings vs calendar):
```

## Per-run writes

1. Generate full consolidation.
2. **Overwrite** `latest.md`.
3. **Append** to `YYYY-MM-DD.md` with header `## Beat HH:MM (slot)` and the same block.

## Git persistence (main-only)

The beat must land on **remote main** after each run. No PR, no delivery worktree.

```bash
INSTANCE="${SECRETARY_INSTANCE:-$(secretary config show | jq -r .instance)}"
cd "$INSTANCE"
git fetch origin main
git checkout main
git pull --rebase origin main
# … write only under subsystem/heartbeat/ …
git add subsystem/heartbeat/
git commit -m "chore(heartbeat): beat $(TZ="$(secretary config show | jq -r '.timezone // UTC')" date +%Y-%m-%d\ %H:%M)"
git push origin main
```

- **Ambient tier:** no human gate, no `sec-merge` for the beat.
- **Precondition:** checkout on `main`, clean except heartbeat files.
- **Conflicts:** if a PR touched `subsystem/heartbeat/`, remove heartbeat from that PR; main wins on `latest.md`. Daily log keeps all `## Beat` blocks in order.
- Spec: `$INSTANCE/_diseño/specs/008-sec-heartbeat/spec.md` § main policy.

## Delta logic

- Base: previous beat (`latest.md` before overwrite or last daily block).
- Classify: **New** / **Closed** / **State changes**.
- No previous beat → mark delta as "initial baseline".

## Interactive narrative

When invoked in chat, respond in 3–6 bullets: what changed, orphans detected, human blockers. Do not reprint the full file unless asked.

## Limits

- Do not close actions automatically.
- Do not write wiki (durable promotion is `wiki-update`).
- Do not send messages to third parties.

## Atomic ops

```bash
secretary config path operations.heartbeat
secretary config path operations.wip
secretary paths
```

Ingest paths (`extractors/*/memory`, etc.) resolve the same way via `secretary config path <key>`.
