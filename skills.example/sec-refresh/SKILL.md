---
name: sec-refresh
description: >-
  Re-entry failsafe after disconnect — connectivity, healthy harness, fresh memory, ordered WIP,
  idempotent brief. Repair to best state, not read-only. Triggers: "/sec-refresh", "I'm back",
  "catch everything up", "secretary failsafe", after long disconnect, or when pulse/sec-state
  show stale signals.
user-invocable: true
---

# sec-refresh — re-entry failsafe

**Repair orchestrator**, not a read-only snapshot. When the owner returns after disconnect (machine off,
travel, dead session), this skill ensures secretary is connected, healthy, fresh, WIP legible, and the
daily brief at best state — **without duplicating** the daily issue.

## Principles

- **Repair to best state.** Unlike `pulse` (read) and `sec-state` (observe wip), `sec-refresh` runs or
  delegates fixes: fetch, validators, extractor pipeline, heartbeat, PR babysit, brief refresh.
- **Re-entry, not close.** Unlike `wind-down` (closes session), this skill **opens** day/session.
- **Brief idempotency.** One open issue with `brief.label` per calendar day (`timezone` from config).
  If it exists, **update** the same number; never create a duplicate.
- **Automatic vs gate.** No third-party touch or merge without human OK stays behind 🚧.
- **Freshness from `origin/main`.** Same as `pulse`: `git fetch origin` before reading evidence.
  Main checkout must be on `main` (worktree discipline for branch work).
- **One sweep, tables per phase.** Empty category → `— none —`; do not omit tables.

## Skill chain

| Need | Skill / action | Role in sec-refresh |
|---|---|---|
| Progress snapshot (no mutate) | `pulse` | **After** phase 5 — validate refresh |
| WIP board only | `sec-state` | Phase 4 — read; if empty/stale, suggest `sec-write` |
| Session close | `wind-down` | **Do not** invoke — opposite intent |
| Operational beat | `sec-heartbeat` | Phase 3 — writes `subsystem/heartbeat/` |
| Merge-ready PRs | `babysit` | Phase 4 — CI/conflicts; **no merge** |
| Merge with human OK | `sec-merge` | Only if owner requests merge same session |
| Morning catch-up | `pre-brief-pipeline.sh` | Phase 3 — after downtime |
| Brief from scratch | `secretary-briefing` | Phase 5 — create or idempotent refresh |
| Chat-reported progress | `secretary status` | Persist if owner reports during refresh |

## Canonical path keys (spec 012)

| Domain | Key / relative path |
|---|---|
| Mail | `extractors/mail/` (`state.md`, `memory/`, `drafts/`, `policy.md`) |
| Meetings | `extractors/meetings/` (`memory/`, `summaries/`) |
| Drive | `extractors/drive/memory/` |
| Job search | `loops/job-search/` (`applications.md`, `inbox.md`) |
| Wiki | `knowledge/wiki/articulos/` |
| Beat | `subsystem/heartbeat/latest.md` |
| WIP | `subsystem/wip/` |
| Brief template | `templates/brief-body.md` |
| Pipeline | `scripts/routines/pre-brief-pipeline.sh` |
| Freshness | `scripts/routines/extractor-freshness.sh` |

Resolve absolute paths: `secretary config path <key>`. In scheduled routines, expand `$WT` before subagent prompts.

Doctrine: `rules/skills-contract.md`

---

## Procedure — five phases

### Instance setup

```bash
CFG=$(secretary config show)
export SECRETARY_INSTANCE="${SECRETARY_INSTANCE:-$(echo "$CFG" | jq -r .instance)}"
export SECRETARY_CORE="${SECRETARY_CORE:-$(echo "$CFG" | jq -r .core)}"
TIMEZONE=$(echo "$CFG" | jq -r '.timezone // "UTC"')
TODAY=$(TZ="$TIMEZONE" date '+%Y-%m-%d')
BRIEF_REPO=$(echo "$CFG" | jq -r '.brief.repo // empty')
BRIEF_LABEL=$(echo "$CFG" | jq -r '.brief.label // "tipo:informe-diario"')
if [ -z "$BRIEF_REPO" ]; then
  BRIEF_REPO=$(gh -R "$SECRETARY_INSTANCE" repo view --json nameWithOwner -q .nameWithOwner)
fi
PERSONAL_ACCOUNT=$(echo "$CFG" | jq -r '.accounts.personal // empty')
WORK_ACCOUNT=$(echo "$CFG" | jq -r '.accounts.inspiro // .accounts.work // empty')
HARNESS_TASKS="${SECRETARY_SCHEDULED_TASKS:-$HOME/.claude/scheduled-tasks}"
```

### Phase 1 — Connectivity

Check external surfaces respond. Log failures; do not abort the full sweep.

```bash
git -C "$SECRETARY_INSTANCE" fetch origin -q
git -C "$SECRETARY_INSTANCE" branch --show-current
git -C "$SECRETARY_INSTANCE" rev-list --left-right --count main...origin/main

[ -n "$PERSONAL_ACCOUNT" ] && gog gmail search 'newer_than:1d' --account="$PERSONAL_ACCOUNT" --max 1 --plain --no-input

[ -n "$WORK_ACCOUNT" ] && gog gmail search 'newer_than:1d' --account="$WORK_ACCOUNT" --max 1 --plain --no-input 2>/dev/null \
  && echo work-account:ok || echo work-account:skip

[ -n "$PERSONAL_ACCOUNT" ] && gog drive ls --account="$PERSONAL_ACCOUNT" --max 1 --plain --no-input 2>/dev/null | head -1

curl -sf http://127.0.0.1:9477/health 2>/dev/null && echo secd:ok || echo secd:skip
```

`401` / `invalid_grant` from `gog` → report re-login (instance `CLAUDE.md` § accounts); mark 🚧.

#### Phase 1 report

```markdown
## 🔄 Phase 1 — Connectivity

| Surface | State | Detail / action |
|---|---|---|
| git main vs origin/main | ✅ / ⚠️ / 🚧 | N commits behind |
| gog personal | ✅ / 🚧 | |
| gog work | ✅ / skip / 🚧 | |
| gog drive | ✅ / 🚧 | |
| secd /health | ✅ / skip / 🚧 | |
```

### Phase 2 — Healthy harness

```bash
secretary validate 2>&1 || true
python3 "$SECRETARY_INSTANCE/scripts/ci/validate_ordenamiento.py" 2>&1 || true
python3 "$SECRETARY_INSTANCE/scripts/ci/validate_paths.py" 2>&1 || true
python3 "$SECRETARY_INSTANCE/scripts/ci/validate_module_contract.py" 2>&1 || true
python3 "$SECRETARY_INSTANCE/scripts/ci/contract_health.py" 2>&1 || true
"$SECRETARY_INSTANCE/scripts/routines/extractor-freshness.sh" 2>&1 || true

# Routines harness — api-cron only (LaunchAgents). Flag if executor != api-cron.
ROUTINES_EXEC=$(echo "$CFG" | jq -r '.dispatch.routines.executor // "api-cron"')
if [ "$ROUTINES_EXEC" = "api-cron" ]; then
  echo "routines executor: $ROUTINES_EXEC"
else
  echo "WARN: dispatch.routines.executor=$ROUTINES_EXEC — verify single scheduler (see operational/routines-executor.md)"
fi

# Dual-scheduler checklist (spec 016) — detect both schedulers armed for the same routine.
launchctl list 2>/dev/null | grep 'com.alvaromur.secretary.routine\.' || echo "no LaunchAgents loaded"
```

Cross-check against Claude Code's own scheduler in-session (not shell-visible): call
`mcp__scheduled-tasks__list_scheduled_tasks` and compare its routine ids against the
`com.alvaromur.secretary.routine.<id>` LaunchAgents just listed.

- `ROUTINES_EXEC=claude-scheduled` **and** any `com.alvaromur.secretary.routine.*` LaunchAgent is
  loaded → 🚨 duplicate scheduler (LaunchAgents should have been removed by
  `install-routine-schedule.sh`; the local `run-routine.sh` will still fire it).
- `ROUTINES_EXEC` is `api-cron`/`cursor-cron` **and** `list_scheduled_tasks` returns an *enabled*
  Claude Code entry for a routine id that also has a loaded LaunchAgent → 🚨 duplicate scheduler
  (both routers will fire the same playbook, double PRs + double billing).
- Mismatch between `ROUTINES_EXEC` and which LaunchAgents are actually loaded (e.g. executor says
  `api-cron` but no `com.alvaromur.secretary.routine.*` is loaded) → ⚠️ stale install, re-run
  `install-routine-schedule.sh`.
- No overlap found → ✅.

Audit scheduled playbooks for legacy path strings (flag, don't hotfix unless obvious typo):

```bash
rg -l 'extractores/|memoria/wiki|operaciones/|/borradores/' "$HARNESS_TASKS" 2>/dev/null || true
```

Untracked legacy folders on disk breaking `validate_ordenamiento` → report as local residue, not `main`.

#### Phase 2 report

```markdown
## 🔄 Phase 2 — Healthy harness

| Check | State | Output / note |
|---|---|---|
| secretary validate | ✅ / ⚠️ | |
| validate_ordenamiento | ✅ / ⚠️ | |
| validate_paths | ✅ / ⚠️ | |
| validate_module_contract | ✅ / ⚠️ | schema + kind |
| contract_health | ✅ / ⚠️ | `module \| kind \| health \| gap` table |
| Playbooks with legacy paths | — none — / list | |
| extractor-freshness | ✅ / ⚠️ | |
| routines executor | ✅ / ⚠️ | `dispatch.routines.executor` |
| Dual-scheduler overlap (spec 016) | ✅ / 🚨 | routine ids present in **both** LaunchAgents and Claude `list_scheduled_tasks` |
```

**Contract health checklist** (spec 015 §4.3): for each `extractors/*/contract.yaml` and `loops/*/contract.yaml`, `contract_health.py` compares extractor `freshness` vs SLA and loop `success_criteria` vs source files (job-search weekly count from `applications.md`). Surface stale extractors and behind criteria in this phase report before phase 3 catch-up.

### Phase 3 — Fresh memory

Reuse **pre-brief-pipeline** pattern. After long downtime, force catch-up.

**Automatic:**

```bash
PRE_BRIEF_FORCE=1 "$SECRETARY_INSTANCE/scripts/routines/pre-brief-pipeline.sh"
```

Runs (per stale/force): `drive-crawler`, `housekeeping`, `job-search-crawler`, `revision-correo`
(if `state.md` stale), `reuniones-update`, optional `wiki-update` if `PRE_BRIEF_RUN_WIKI=1`, closes
with `sec-heartbeat` pre-brief slot.

**Gated 🚧:**

| Routine | Why gated |
|---|---|
| `revision-correo` (send) | Drafts OK; **send** needs explicit OK |
| `wiki-update` | Heavy; default off in morning pipeline |
| `whatsapp-monitor` | Report only if stream down |

If pipeline cannot run, delegate individual routines via `run-routine.sh <id>`.

Verify beat:

```bash
head -40 "$(secretary config path operations.heartbeat)/latest.md"
```

If missing or >3h stale on workday → invoke `sec-heartbeat` in session.

#### Phase 3 report

```markdown
## 🔄 Phase 3 — Fresh memory

| Extractor / routine | Action | Result |
|---|---|---|
| drive-crawler | run / skip | PR / fresh |
| sec-heartbeat | run | latest.md timestamp |
```

### Phase 4 — Ordered WIP

Read state; push PRs to merge-ready. **Do not merge** without `sec-merge` + OK.

1. **WIP board** — `sec-state` or `subsystem/wip/`.
2. **Heartbeat matches** — `loose-acc` / `loose-git` rows.
3. **Open PRs** — allowlist from config plus instance repo:

```bash
gh pr list --repo "$BRIEF_REPO" --state open --json number,title,headRefName,isDraft,statusCheckRollup
# Repeat per dispatch.executor.repos entry
```

4. CI red / conflicts / unresolved human comments → `babysit`. No merge.
5. If main checkout not on `main` → **alert** (stale reads); recommend worktree for branch work.

#### Phase 4 report

```markdown
## 🔄 Phase 4 — Ordered WIP

| PR | Repo | State | Action | Blocker |
|---|---|---|---|---|
| — none — | | | | |
```

### Phase 5 — Idempotent brief

**Rule:** at most **one** issue with `brief.label` whose title contains `$TODAY`.

```bash
BRIEF_JSON=$(gh issue list --repo "$BRIEF_REPO" --label "$BRIEF_LABEL" --state all \
  --json number,title,createdAt,state \
  --jq --arg d "$TODAY" '[.[] | select(.title | contains($d))] | sort_by(.createdAt) | last')

BRIEF_NUM=$(echo "$BRIEF_JSON" | jq -r '.number // empty')
```

- Multiple issues same date → 🚨 report duplicate; keep newest canonical.
- Empty `BRIEF_NUM` → create (5.3).
- Exists → refresh (5.2).

#### 5.2 — Refresh existing

```bash
BRIEF_REFRESH_ISSUE="$BRIEF_NUM" BRIEF_REFRESH_VIA=sec-refresh PRE_BRIEF_SKIP_PIPELINE=1 \
  "$SECRETARY_INSTANCE/scripts/routines/run-routine.sh" secretary-briefing
```

Preserves existing `sec-status` comments. Fallback: `gh issue edit` — never duplicate `gh issue create`.

#### 5.3 — Create (only if none today)

```bash
PRE_BRIEF_SKIP_PIPELINE=1 "$SECRETARY_INSTANCE/scripts/routines/run-routine.sh" secretary-briefing
```

#### 5.4 — Close phase

Optional: invoke `pulse` to validate brief vs evidence.

#### Phase 5 report

```markdown
## 🔄 Phase 5 — Idempotent brief

| Field | Value |
|---|---|
| Issue | #N — url |
| Action | create / refresh / fix-duplicate |
```

---

## Automatic vs requires OK

| Action | Automatic | Requires OK |
|---|---|---|
| `git fetch` / `git pull` on main | ✅ | |
| `secretary validate` | ✅ | |
| `pre-brief-pipeline` (force) | ✅ | |
| `sec-heartbeat` commit+push main | ✅ | |
| `babysit` | ✅ | |
| Create/edit brief issue | ✅ | |
| Send mail/WhatsApp | | 🚧 |
| Merge PRs | | 🚧 |
| Mutate remote Drive | | 🚧 |
| Commit on instance | | Only if owner asks |

---

## When to use / not use

- **Use:** `/sec-refresh`, "I'm back", after long disconnect, stale pulse/sec-state.
- **Not:** read-only progress → `pulse`; close session → `wind-down`; entity recall → `sec-recall`.

## Do not

- Merge PRs without explicit OK.
- Send mail or messages to third parties.
- Commit on instance unless owner asks (heartbeat main-only is routine exception).
- Create a second brief for the same calendar day.
- Pass unexpanded `secretary/` paths to subagents in scheduled runs.
