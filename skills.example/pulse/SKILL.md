---
name: pulse
description: >-
  Briefing-anchored progress snapshot AND work on-ramp. Invoke anytime: cross the daily brief against
  real evidence (completed items inferred, not checkbox-only), auto-dispatch status, and in-flight
  work across sessions with git stage. Optionally hydrate one item to start working. Replaces day-start.
  Triggers: "/pulse", "/day-start", "how am I doing", "daily progress", "what's on today",
  "where do we start", "day pulse".
user-invocable: true
---

# pulse — progress snapshot + on-ramp

**Mission:** the single skill anchored to the daily brief. Two flows:

1. **STATUS (always):** progress picture at any hour — what's done, what's running (dispatches), what's in flight and at which git stage.
2. **ON-RAMP (optional, end):** hydrate ONE item — load repo context, handover/WIP, issue/PR body — and offer to start ("ready?").

**Why evidence, not checkboxes:** the owner often advances work without ticking boxes. Pulse crosses real evidence (merged PR, closed issue, dispatch:done, sends, files created).

## Modes

- **Interactive (default):** invoked by the owner in session. Full STATUS report inline + ON-RAMP offer at the end (step 6).
- **Headless (`PULSE_HEADLESS=1`):** invoked by the `pulse-headless` scheduled task, no owner present. Runs **STATUS only** (steps 1–5, including 3.7) — skip ON-RAMP (step 6) and the hydration offer entirely, since there's no one to answer "which item?". Output is **posted as a comment** on today's brief issue instead of printed inline — see `~/.claude/scheduled-tasks/pulse-headless/SKILL.md` for the delivery mechanism. Same evidence rules, same report format, minus the closing question.

## Guardrails

- **Read-only, with two named exceptions.** No checkbox edits, commits, merges. Hydration loads context only — does not execute. The two writes this skill performs, both opt-in/explicit: (1) headless mode posts its STATUS report as an issue comment (§ Modes); (2) ON-RAMP step 6.5 appends to `subsystem/dream/queue.md` only when the owner explicitly approves during hydration. Neither touches brief checkboxes, code, or any other file.
- **Freshness — read from `origin/main`, NOT your session branch.** Always `git fetch origin` first; read evidence with `git show origin/main:<path>`. Working tree only for the **unsaved** block. Scan open `auto-*` PRs for capture not yet on main.
- **Evidence ≠ git only.** Personal items (send, apply, schedule) live in module `memory/`, `state.md`, `loops/job-search/applications.md`, brief **Secretary — dispatch & deliveries** (`Tipo: entregado`), and `sec-status` comments. Scan all before marking pending. Cite sources.
- **Done vs done-but-unsaved.** Git stage is key: dirty working tree = at risk; in PR/merged = safe.

## Optional argument

Keyword, issue/PR number, or description → skip wide status, go to **hydrate that item** (step 6). No argument → full status + on-ramp offer.

## Procedure

### Instance setup

```bash
CFG=$(secretary config show)
INSTANCE="${SECRETARY_INSTANCE:-$(echo "$CFG" | jq -r .instance)}"
TIMEZONE=$(echo "$CFG" | jq -r '.timezone // "UTC"')
TODAY=$(TZ="$TIMEZONE" date '+%Y-%m-%d')
BRIEF_REPO=$(echo "$CFG" | jq -r '.brief.repo // empty')
BRIEF_LABEL=$(echo "$CFG" | jq -r '.brief.label // "tipo:informe-diario"')
if [ -z "$BRIEF_REPO" ]; then
  BRIEF_REPO=$(gh -R "$INSTANCE" repo view --json nameWithOwner -q .nameWithOwner)
fi
HEARTBEAT_LATEST=$(secretary config path operations.heartbeat)/latest.md
DEFAULT_OWNER="${BRIEF_REPO%%/*}"
```

### 1 — Heartbeat (loose work)

`subsystem/heartbeat/` lives **main-only** (spec 008). Read live `latest.md` at `$HEARTBEAT_LATEST` — not a session-branch copy.

If `latest.md` exists and timestamp is recent (≤3h on a workday, or pre-brief beat today), read before ad-hoc git scan:

```bash
head -30 "$HEARTBEAT_LATEST"
```

Extract **Match acc↔git** rows with `match ∈ {loose-acc, loose-git}`:

| match | On-ramp offer |
|-------|----------------|
| `loose-acc` | Hydrate acc + Cowork context; or draft PR path if code on allowlist |
| `loose-git` | Link to existing acc; or suggest issue/dispatch (propose only) |
| `linked` | Skip by default — already in brief **Work in flight** |

If heartbeat missing/stale, continue steps 2–3. Don't duplicate `linked` rows already in the brief.

### 2 — Load the map (today's brief)

```bash
ISSUE_NUM=$(gh issue list --repo "$BRIEF_REPO" --label "$BRIEF_LABEL" --state all \
  --json number,createdAt --jq 'sort_by(.createdAt) | last | .number')
gh issue view "$ISSUE_NUM" --repo "$BRIEF_REPO" --json body,title,url,state
```

Extract **Your list for today** (`- [ ]` / `- [x]`). Brief is the **order** — v2.1 puts this section first.

**Section map (template v2.1):**
- **Your list for today** — primary order map.
- **Work in flight** — unified table (Repo · Branch · PR · Situation · Relation & next step). `Situation` ∈ `in flight` / `just merged` / `needs push`. **Repo** column: slug by default; `owner/repo` only if owner ≠ default or ambiguous.
- **Waiting on others** — follow-ups in someone else's court.
- **Secretary — dispatch & deliveries** — unified table with `Type` (`executed` / `candidate` / `delivered`).
- **Run summary** — team metrics (secondary; not the order map).

**v1 compatibility:** map legacy headers (`Executive summary`, old dispatch blocks, `Loose threads`) to v2.1 logic.

If no brief today: say so; fall back to dispatch + git pulse.

**`sec-status` comments — first-class evidence:**

```bash
gh issue view "$ISSUE_NUM" --repo "$BRIEF_REPO" --json comments \
  --jq '.comments[] | select(.body | contains("claude-generated:sec-status")) | .body' | grep "sec-status ·"
```

Each `sec-status · <date> · <emoji> <ref> — <note>` line wins over inference.

### 3 — Auto-dispatch status

From config `dispatch.executor.repos`, per repo list issues with labels `dispatch:execute|running|done|blocked`. For each `done`/`blocked`, find closing PR. Highlight `blocked`.

### 3.5 — Evidence sweep (from main)

```bash
git -C "$INSTANCE" fetch origin --quiet
git -C "$INSTANCE" show origin/main:extractors/mail/state.md
git -C "$INSTANCE" show origin/main:extractors/mail/memory/$TODAY.md
git -C "$INSTANCE" show origin/main:extractors/meetings/memory/acciones.md
git -C "$INSTANCE" show origin/main:loops/job-search/applications.md
```

**Today's `mail/auto-*` PRs** — before marking mail items pending:

```bash
gh pr list --repo "$BRIEF_REPO" --state all \
  --json number,title,headRefName,state,body,mergedAt,createdAt \
  --jq '.[] | select(.headRefName | test("^mail/auto-|^correo/auto-")) | select(.createdAt | startswith("'"$TODAY"'") or (.mergedAt // "" | startswith("'"$TODAY"'")))'
```

Cross personal brief items against these sources + `Type: delivered` rows + brief comments.

### 3.6 — Module contract health (spec 015)

After evidence sweep, audit each module `contract.yaml` for operational health:

```bash
python3 "$INSTANCE/scripts/ci/validate_module_contract.py" 2>&1 || true
python3 "$INSTANCE/scripts/ci/contract_health.py" 2>&1
# JSON for scripting:
python3 "$INSTANCE/scripts/ci/contract_health.py" --format json
```

**Checklist:**

1. **Schema** — `validate_module_contract` (presence, kind, forbidden fields, routine in manifest).
2. **Extractors** — compare `freshness.last_success_at` vs `freshness.sla` (2× window heuristic in `contract_health.py`).
3. **Loops** — read `success_criteria[].source`; compute `current` vs `target` where parseable (job-search: weekly `**N/M**` in `applications.md`).
4. **Submodules** — loop `submodules[].iteration_ledger` mtime vs submodule `freshness.sla` when present.

Include in the pulse report (after dispatch, before loose work):

| module | kind | health | gap |
|--------|------|--------|-----|

`health` values: `ok` · `stale` (extractor SLA) · `behind` (loop criteria) · `paused` · `warn` · `unknown`.

Doctrine: `_diseño/specs/015-module-contract/spec.md` §4.3.

### 3.7 — Scheduled tasks health

Read `.cursor/routines/manifest.yaml` (`$INSTANCE/.cursor/routines/manifest.yaml`) — the registry
of cron routines. For each routine, cross its cron against **actual recent activity** to answer:
last run, on-time or behind, and whether it's on a dry streak worth flagging.

This is **report-only** — pulse never touches a routine's own escalation/retry behavior (that's
spec `_diseño/specs/L5-observabilidad/024-recurrencia-escalacion/spec.md`). It just makes silent
drift visible.

**Two signal shapes — check which one a routine uses before assuming PR-per-run:**

Per spec 024 ("un run sin cambio de fondo no debe generar un PR"), several routines already use
module store / ambient main when there is no real change. **Check both shapes** — don't assume
PR-per-run everywhere:

| routine id | signal today | where |
|------------|--------------|-------|
| `drive-crawler` | PR (not yet migrated) | `extractors/drive/auto-*` |
| `housekeeping` | PR only if hay algo que decidir; else ambient / sin PR (spec 024) | `subsystem/housekeeping/auto-*` |
| `job-search-crawler` | PR solo con reportables; seco → `recurrence.yaml` ambient (spec 024) | `loops/job-search/auto-*` + `loops/job-search/sources-web/recurrence.yaml` |
| `sales-crawler` | PR (not yet migrated) | `loops/sales/auto-*` |
| `revision-correo` | PR if porcelain; else sin PR | `extractors/mail/auto-*` or `correo/auto-*` |
| `reuniones-update` | PR if porcelain; else sin PR | `extractors/meetings/auto-*` or `reuniones/auto-*` |
| `wiki-update` | PR if porcelain; else sin PR | `knowledge/wiki/auto-*` |
| `tidy-up` | PR solo con cambio de fondo; racha en store (spec 024) | `subsystem/housekeeping/tidy-up-*` + `subsystem/housekeeping/memory/recurrence.yaml` |
| `soltrak-correo` | PR solo con movimientos (inspiro; spec 024) | `cowork-inspiro` digests / PRs |
| `secretary-briefing` | Issue | label `tipo:informe-diario`, latest `createdAt` |
| `dispatch-executor` | Issue | label `dispatch:execute\|running\|done\|blocked`, latest activity |
| `sec-heartbeat` | file mtime | `subsystem/heartbeat/latest.md` (main-only, no PR) |
| `sec-dream` | **module store, not PR** for skip puro | `subsystem/dream/latest.json` + `log/YYYY-MM-DD.md` (main-only ambient); real `dream_job` → PR in *target* repo |
| `reuniones-scheduler` | — | poll-only — covered by `reuniones-update`, skip |
| `pulse-headless` | Issue comment | brief del día (`agent-generated:pulse-headless`) |

```bash
# PR-signaled routines (still one PR per run):
gh pr list --repo "$BRIEF_REPO" --state all --limit 30 \
  --json number,title,headRefName,state,createdAt,mergedAt,body \
  --jq '.[] | select(.headRefName | test("^<pattern>"))' | jq -s 'sort_by(.createdAt) | reverse | .[0:6]'
# Issue-signaled routines:
gh issue list --repo "$BRIEF_REPO" --label "<label>" --state all \
  --json number,createdAt --jq 'sort_by(.createdAt) | reverse | .[0:6]'
# sec-heartbeat (file mtime, no PR):
git -C "$INSTANCE" log -1 --format=%cI -- subsystem/heartbeat/latest.md
# sec-dream (module store, no PR for skips):
git -C "$INSTANCE" show origin/main:subsystem/dream/latest.json | jq '.date, .dream_job, .skipped_no_owner_job.reason // empty'
ls "$INSTANCE"/subsystem/dream/log/ | tail -6   # recent daily logs, for the streak below
```

Compute per routine:

- **Última corrida** — timestamp of the most recent matching PR/issue/commit, or (module-store
  routines) the `date`/mtime of the latest store entry.
- **Al día / atrasada** — compare against the cron's expected interval (parse `cron` field loosely:
  daily crons → 1 day + reasonable slack; weekday-only or weekly crons → their own cadence, not
  calendar days). Flag `atrasada` when the gap clearly exceeds the cron's own cadence, not on a
  single missed slot.
- **Racha seca (fallback heurístico)** — only when the routine has **no** `recurrence.yaml` yet:
  among the last 5–6 matching PRs, count consecutive ones whose body/title says "sin cambios",
  "skipped", "no candidates", or similar no-op language. For `sec-dream`: count consecutive
  `dream_job.status == "skipped_no_owner_job"` across `dream-YYYYMMDD.json`/log. `≥5` consecutive
  → flag `necesita atención`.
- **Recurrencia (spec 024, SC-2) — prefer this when the store exists.** Read each module's
  `recurrence.yaml` from `origin/main` (after `git fetch`). Do **not** re-derive rachas from PR
  bodies when this file is present.

```bash
N=3   # umbral del contrato; "a un paso" = streak >= N-1
# Known stores (extend if a module adds its own):
git -C "$INSTANCE" show origin/main:subsystem/housekeeping/memory/recurrence.yaml
git -C "$INSTANCE" show origin/main:loops/job-search/sources-web/recurrence.yaml
```

Per finding under `findings:`:

| Campo | Uso en pulse |
|-------|----------------|
| `streak` | entero de rachas consecutivas |
| `status` | `open` / `escalated` / `resolved` — ignore `resolved` for alerts |
| `class` | `resuelve-solo` / `escala` (informativo en el reporte) |
| `last_seen` | fecha de la última corrida con el hallazgo |
| `issue` | si está escalado, citar el número |

Alertas (columna **racha seca** / nota):

| Condición | Flag |
|-----------|------|
| `status ∈ {open, escalated}` y `streak >= N-1` (default 2) | `necesita atención` — "a un paso de escalar" (o ya escaló si `status: escalated`) |
| `status: escalated` | citar `issue` aunque streak ya haya bajado |
| `status: resolved` | no alertar por ese fingerprint |

Map routine ↔ store:

| routine id | recurrence.yaml |
|------------|-----------------|
| `tidy-up` | `subsystem/housekeeping/memory/recurrence.yaml` |
| `job-search-crawler` | `loops/job-search/sources-web/recurrence.yaml` |
| others | none yet → keep PR/no-op heuristic above |

Don't over-engineer parsing — this is a heuristic cross-check for the owner, not a monitoring
system. When a routine's manifest entry or activity is ambiguous, report `sin señal clara` rather
than guessing.

### 4 — Work in flight + git stage + unmerged capture

Read **Work in flight** from brief; supplement with worktrees/branches:

```bash
git -C <repo> worktree list
git -C <repo> status -sb
git -C <repo> log --oneline @{u}..HEAD 2>/dev/null
gh pr list --repo <owner/repo> --state open --json number,title,headRefName,isDraft,reviewDecision
```

Map each thread to git stage: `uncommitted` · `committed unpushed` · `branch no PR` · `PR draft` · `PR ready` · `merged` · `pruned`. Early stages → **unsaved** block. Open `auto-*` PRs = **tentative capture**.

**Frentes por hilo (Cowork workspaces with multiple parallel projects, e.g. `ennui`, `inspiro`):** a single repo can host several unrelated threads (client projects). Don't flatten them into one PR list — group by front:

```bash
gh label list --repo <owner/repo> --search "hilo:" --json name --jq '.[].name'
```

- If `hilo:<scope>` labels exist, group PRs by label:
  ```bash
  gh pr list --repo <owner/repo> --state all --limit 200 \
    --json number,title,state,labels,updatedAt
  ```
  then bucket by each PR's `hilo:*` label (a PR with none → `sin-hilo`).
- If the repo has no `hilo:` labels yet, fall back to the Conventional Commit scope in the title (`^\w+\(([^)]+)\):`) as a proxy grouping — but flag it as unlabeled and suggest adopting `hilo:` labels (see `~/.claude/CLAUDE.md` § "Etiquetas de GitHub para hilos y series") rather than treating the proxy as durable.
- Per front, report: most recent PR (number + state), total PR count, and whether the latest PR is open/merged — this is the "chain" view, not just the flat brief list.

### 5 — Cross and report status

Per brief item: ✅ **done** (cite evidence) · 🔄 **in flight** (git stage) · ⏳ **pending**.

Include **Loose work** block from heartbeat if any. Close offering on-ramp: **"Which item should I hydrate?"** — prioritize `loose-acc` with today's deadline, then stale `loose-git`.

### 6 — Hydrate one item (on-ramp, optional)

When the user picks an item (or passed as argument):

a) **Prior WIP:** `secretary config path operations.wip`; load matching handover if any.
b) **Artifact:** `gh issue view` / `gh pr view` / acciones.md entry.
c) **Repo context:** read `CLAUDE.md`, `git branch --show-current`, `git status -sb`, `git log --oneline -5`.
d) **Orient and stop:** compact brief below; close with "ready to start?". Do not execute.

### 6.5 — Offer to queue for `sec-dream` (optional, only on explicit approval)

When the hydrated item (or any item surfaced in STATUS) is real work the owner **approves but
doesn't want to start now** ("queue that for tonight", "let dream pick this up"), offer to add it
to `subsystem/dream/queue.md` instead of just noting it. Only write on explicit yes — this is the
one place pulse writes outside its own report.

Format — append one entry under `## Pendientes` (oldest first is priority order, so append at the
bottom of the section, not the top):

```markdown
### [2026-09-12] <lane/short title>
- **Fuente:** pulse on-ramp 2026-09-12
- **Contexto:** <1-3 lines — what sec-dream should do, why it's ready>
- **Repo/lane:** <repo slug or lane name, if known>
- **Prioridad:** alta | media
```

`sec-dream` reads this file first in its Phase 1 (before its own scoring) and removes the entry it
consumes — see `~/.claude/skills/sec-dream/SKILL.md` § Phase 1. Pulse only ever appends; it never
removes or reorders existing entries.

## Report

Inline, expressive (`rules/sec-output.md`). Header: `🧭 **Pulse — <date>** · vs Briefing #N`.

```markdown
🧭 **Pulse — 2026-06-11** · vs Briefing #N · <time>

**Your list (from brief)**

| # | Item | State | Where / git stage |
|---|------|-------|-------------------|
| 1 | … | ✅ done | PR #232 merged |
| 2 | … | 🔄 in flight | branch `feat/x` · PR draft |
| 3 | … | ⏳ pending | — |

**Secretary — dispatch & deliveries**

| Type | What | Repo | State |
|------|------|------|-------|
| executed | … | instance-slug | issue #231 · PR #232 awaiting review |

**Dispatches on GitHub** (allowlist — `dispatch:*` issues)

| Issue | Repo | State | PR / note |
|-------|------|--------|-----------|

**Module contract health** (spec 015 — `contract_health.py`)

| module | kind | health | gap |
|--------|------|--------|-----|

**Salud de rutinas programadas** (manifest.yaml vs actividad reciente)

| rutina | última corrida | al día | racha seca |
|--------|-----------------|--------|------------|

**Loose work** (heartbeat — `loose-*` matches)

| match | acc-id / ref | Repo | Note |
|-------|--------------|------|------|

**Unsaved** (at risk — early git stage)

| Repo | Branch | Stage | What |
|------|--------|-------|------|

**Frentes por hilo** (workspace repos with multiple parallel projects — omit table if the repo has one thread only)

| Frente | Último PR | Estado | Total PRs |
|--------|-----------|--------|-----------|

**Summary:** X/Y brief done · Z dispatches · N loose · M unsaved · K rutinas necesitan atención

> Which item should I hydrate? (number or topic)
```

Hydration brief (step 6): `📋 **Working on: [title]**` + repo/branch/WIP/capture context + `> Ready. Start?`

Report rules:
- **Repo** column: slug by default; full `owner/repo` only when non-default owner or ambiguous (`DEFAULT_OWNER` from brief repo).
- Empty sections → `— none —`; do not omit.
- **Unsaved** first among alerts when non-empty.
- No coaching. Never tick brief checkboxes — that's the owner's gesture.
- **Headless mode:** omit the closing `> Which item should I hydrate?` line entirely (§ Modes) — post everything above it as the comment body.

## When to use / not use

- **Use:** anytime for progress; at desk start for on-ramp.
- **Not:** raw WIP without brief spine → `sec-state`. Entity knowledge → `sec-recall`.

## Atomic ops

```bash
secretary config show
secretary config path operations.heartbeat
secretary paths
secretary status "✅" "#1" "note"   # persist progress (not pulse's job to call)
```

Heartbeat path: `secretary config path operations.heartbeat`/latest.md
Dream queue path: `$INSTANCE/subsystem/dream/queue.md` (step 6.5 — pulse only appends)
Scheduled routines registry: `$INSTANCE/.cursor/routines/manifest.yaml` (step 3.7 — read-only)
Headless delivery playbook: `~/.claude/scheduled-tasks/pulse-headless/SKILL.md`
