---
name: desk-drone
description: >-
  Brings secretary's full context into any repo: locates the active zone, checks what's stale,
  recalls topic memory, and routes to the right skill for the actual work. Triggers: "/desk-drone",
  "bring secretary", "secretary companion", "what do we know about", "quiero cerrar",
  "help me with", topic-driven work from Cowork/Dev repos when full instance context is needed.
---

# desk-drone

**What this does:** when invoked in any repo (Cowork, Dev, or the instance), this skill gives the
session secretary's context on a topic — which repo/branch it's in, what's stale, what's known
about the topic, and which skill handles the actual work. It orients, then hands off; it does not
do the work itself.

Doctrine: `rules/skills-contract.md` · Output: `rules/sec-output.md`

## Principles

- Resolve the instance via `secretary config`; never assume `cwd` is the instance.
- The topic (person, org, project) drives what to check — not the daily brief spine (that's `desk-overview`).
- Check proactively. Don't wait for the owner to ask "is mail current?".
- Report gaps and the next skill together, in the same breath — don't make the owner dig.
- Close only the gaps that block the current topic. Full repair is `desk-refresh`.
- After orienting, hand off to a child skill — this skill doesn't execute the work.
- One screen of output, then a clear `→` next step.
- Read `soul.md` (below) at the start of each run.

## Persistent state: soul.md

This skill keeps its own running notes at `secretary config path subsystem.drone`/`soul.md` —
separate from the owner's business objectives in `knowledge/objectives/`.

| Section | Use |
|---------|-----|
| `purpose` / `drive` | Why this skill scans and routes proactively |
| `objectives` | This skill's own goals; `audit` column feeds Phase 2 probes |
| `memory` | Append-only log of conclusions about secretary itself |
| `alignment` | Pointers to owner lanes — read, never duplicate |

Design: `_diseño/arquitectura/drone-soul.md` · schema: `subsystem/drone/README.md`

## Guardrails

- No third-party touch without explicit OK (send mail, merge PR, mutate Drive).
- No instance commits unless the owner asks (heartbeat is the routine-only exception).
- Read-only in Phases 1–3. Phase 2b runs a routine only when stale evidence blocks recall **and**
  the owner hasn't declined — or when the owner explicitly asks to "get current".
- Fresh reads from `origin/main` on the instance checkout before citing routine capture.

## Inputs

| Field | Source | Notes |
|-------|--------|-------|
| `topic` | User message | Person, org, project, negotiation, meeting — required for a full run |
| `host_repo` | `pwd` + config | Mapped to a `dispatch.executor.repos` entry when possible |
| `intent` | Inferred | `orient` (default) · `recall-only` · `catch-up` |

Optional argument: a topic string or `#N` brief ref → skip the wide locate, focus recall on that.

---

## Skill chain (delegation map)

| Signal / need | Delegate to | When |
|---------------|-------------|------|
| Full re-entry repair (disconnect, everything stale) | `desk-refresh` | Owner says "catch everything up", `/desk-refresh`, or multi-surface outage |
| Day progress vs brief | `desk-overview` | "How am I doing today", brief-anchored status |
| Raw WIP board, no topic | `desk-state` | "Where did I leave things" without a subject |
| Entity/topic memory | `desk-recall` | Phase 3 — always for `topic` |
| Meeting just ended / unprocessed | `desk-meeting` | Topic touches a call, participant, or `secretary fresh meeting` shows a gap |
| Live Gmail / reply context | `desk-mail` | Topic touches a mail thread, sender, or `secretary fresh mail` shows a gap |
| Message drafts to a contact | `desk-compose` | Owner ready to write after orienting |
| PR feedback before coding | `pr-sync` | Host repo has an open PR on the current branch |
| Mechanical coding in host repo | `to-cursor` | Operational task scoped to host repo files |
| Persist a conclusion | `desk-write` | Owner confirms a fact should land in memory/wiki |
| Durable secretary/system conclusion | soul `memory` | This skill forms an improvement insight — see Persist |
| Merge-ready PR hygiene | `babysit` | Open PR on topic needs CI/conflict fix |
| Batch low-tier merge (explicit) | `desk-merge` | Owner wants low-friction merge after surfacing |
| Dream overnight PR | surface in Phase 5 | Read `subsystem/dream/latest.json` — suggest `desk-merge` |
| Session close | `wind-down` | Owner wrapping up — not a desk-drone entry |
| Handoff to another session | `handover` | Document state — not a desk-drone entry |
| Offload unrelated idea | `delegate` | Side thread while staying on topic |

---

## Procedure

### Setup

```bash
eval "$(secretary env)"
CFG=$(secretary config show)
export SECRETARY_CORE="${SECRETARY_CORE:-$(echo "$CFG" | jq -r .core)}"
TIMEZONE=$(echo "$CFG" | jq -r '.timezone // "UTC"')
TODAY=$(TZ="$TIMEZONE" date '+%Y-%m-%d')
BRIEF_REPO=$(echo "$CFG" | jq -r '.brief.repo // empty')
[ -z "$BRIEF_REPO" ] && BRIEF_REPO=$(gh -R "$SECRETARY_INSTANCE" repo view --json nameWithOwner -q .nameWithOwner)
HOST_PWD=$(pwd)
WIP_ROOT=$(secretary config path operations.wip 2>/dev/null || secretary config path subsystem.wip)
HEARTBEAT_LATEST="$(secretary config path operations.heartbeat)/latest.md"
DRONE_ROOT=$(secretary config path subsystem.drone 2>/dev/null || secretary config path operations.drone)
SOUL_PATH="${DRONE_ROOT}/soul.md"
OBJECTIVES_ROOT=$(secretary config path knowledge.objectives.root 2>/dev/null || echo "")
```

Read soul **before** host mapping:

```bash
[ -f "$SOUL_PATH" ] && sed -n '/^## purpose/,/^## /p' "$SOUL_PATH" | head -40
```

Read the dream lessons store too — same store `desk-dream` writes to, applies to any agent
interpreting client/owner data (issue cowork-secretary#509):

```bash
LESSONS_PATH="$(dirname "$DRONE_ROOT")/dream/lessons.md"
[ -f "$LESSONS_PATH" ] && cat "$LESSONS_PATH"
```

### Phase 1 — Locate

Load `purpose`, active `objectives`, and `alignment` from `$SOUL_PATH`. Note which objectives have
an `audit` hook relevant to `topic` (freshness, contracts, routines).

```bash
echo "$CFG" | jq -r '.dispatch.executor.repos[] | "\(.repo)\t\(.path)"' \
  | while IFS=$'\t' read -r repo path; do
      expanded=$(eval echo "$path")
      case "$HOST_PWD" in "$expanded"|"$expanded"/*) echo "matched:$repo:$expanded"; esac
    done

[ -n "$OBJECTIVES_ROOT" ] && find "$OBJECTIVES_ROOT/strategy" "$OBJECTIVES_ROOT/relations" \
  -name '*.md' ! -name '_*' 2>/dev/null | head -20
[ -f "$HOST_PWD/AGENTS.md" ] && head -60 "$HOST_PWD/AGENTS.md"
git -C "$HOST_PWD" branch --show-current 2>/dev/null
git -C "$HOST_PWD" status -sb 2>/dev/null | head -5
REPO_SLUG=$(basename "$HOST_PWD")
[ -f "$WIP_ROOT/${REPO_SLUG}.md" ] && head -40 "$WIP_ROOT/${REPO_SLUG}.md"
git -C "$SECRETARY_INSTANCE" fetch origin -q
```

Record: host repo name/slug, branch, dirty state, matching WIP entry, whether the host is on the
delegate allowlist. If `cwd` isn't on the allowlist, still run — note `host: unlisted` and rely on
topic recall.

*(The repo-matching loop above has no dedicated CLI command yet — candidate for `secretary-core`.)*

### Phase 2 — Scan

Probe modules relevant to `topic` (default: quick pass on all extractors):

```bash
secretary fresh all --format json 2>/dev/null || secretary fresh all
python3 "$SECRETARY_INSTANCE/scripts/ci/contract_health.py" --format json 2>/dev/null || true
```

**Topic → extra probe:**

| Topic touches | Extra probe |
|---|---|
| Person, meeting, call | `secretary fresh meeting` → maybe `desk-meeting` step 0 |
| Email, thread, sender | `secretary fresh mail` → maybe `desk-mail` step 0 |
| Drive doc, file | `secretary fresh drive` |
| Job search | `loops/job-search/applications.md` on `origin/main` |
| Brief item `#N` | `gh issue view` on today's brief |
| Any topic (standing) | `find ~/Desktop ~/Downloads -maxdepth 1 -type f ! -name '.*' \| wc -l` — >25 loose files or disk <15% free → suggest `tidy-up` (`operational/orden-local.md`) |

**Unmerged capture** (same pattern as `desk-recall`):

```bash
PAT='^(mail|correo|meetings|reuniones|whatsapp|wiki|housekeeping|job-search|drive)/auto-[0-9]{8}-[0-9]{4}$'
gh pr list --repo "$BRIEF_REPO" --state open --json number,headRefName,title \
  --jq ".[] | select(.headRefName | test(\"$PAT\"))"
```

Filter PRs whose title/diff plausibly matches `topic`.

#### Phase 2b — Catch-up (conditional)

Run only when stale evidence would mislead recall on `topic`:

| Stale signal | Action | Gated 🚧 |
|---|---|---|
| Meeting ended <3h, Tactiq stable, no PR | Offer `desk-meeting` → `reuniones-update` | If heavy |
| `contract_health` flags the touched module | Report; offer targeted routine | Full pipeline |
| Instance `main` behind `origin/main` | `git pull` on instance main | |
| Everything stale post-disconnect | Suggest full `desk-refresh` | |

Never auto-run `secretary-briefing`, send mail, or merge PRs from this skill.

### Phase 3 — Remember

1. `secretary recall "<topic>" --format json` — deterministic index.
2. Run `desk-recall` synthesis on `topic`: wiki → module memory → wip → unmerged PRs.
3. If Phase 2 flagged a live medium, run that medium's step 0 first (`desk-meeting`, `desk-mail`, …).
4. Cross-check heartbeat: `grep -i "<topic-keyword>" "$HEARTBEAT_LATEST" 2>/dev/null`.
5. If `topic` maps to a brief item, pull `sec-status` comments as first-class evidence (`desk-overview` §2).

Mark tentative unmerged facts `⏳ tentative (PR #N)`.

### Phase 4 — Orient

**Align:** map `topic` to an owner lane (soul `alignment` / `knowledge/objectives/`), and to a
soul objective if one applies (`obj-freshness`, `obj-blockers`, …). Then classify:

- **Both** — the topic advances the owner's delivery *and* secretary's own health (e.g. closing a
  stale PR backlog item) → say so explicitly.
- **Owner-only** — normal client/product focus; still surface blocking stale evidence.
- **Conflict** — e.g. a heavy catch-up run costs tokens the owner didn't ask to spend → present
  both paths, default to owner urgency with a cost note, never auto-run gated routines.

**Brief:** synthesize a compact report (see Report below), closing with:

1. **State** — what's true now about `topic` (1–2 sentences).
2. **Gaps** — what's stale, missing, or waiting on others.
3. **→ Next** — one primary skill + trigger phrase; optional secondary.

**Routing heuristics:**

| Owner intent | Primary route |
|---|---|
| Close negotiation / decision work | `desk-recall` done → host `AGENTS.md` + `desk-compose` for drafts |
| Continue code on open PR | `pr-sync` → work in host repo |
| "What happened in the meeting" | `desk-meeting` (if not already run in Phase 2) |
| Daily priorities in this repo | `desk-overview` with topic hydrate |
| Mechanical implementation | `to-cursor` after orient confirms scope |
| Everything feels stale | `desk-refresh` |

Ask one focused question only when `topic` is ambiguous (e.g. two orgs match).

### Phase 5 — Git & merge surfacing (when host or topic has open PRs)

```bash
git -C "$HOST_PWD" status -sb
git -C "$HOST_PWD" branch -vv | head -15
gh pr list --repo "$(git -C "$HOST_PWD" remote get-url origin 2>/dev/null | sed -n 's/.*github.com[:/]\(.*\)\.git/\1/p')" \
  --state open --json number,title,headRefName,mergeable 2>/dev/null || true
git -C "$SECRETARY_INSTANCE" branch --show-current
DREAM_LATEST="$(secretary config path subsystem.dream 2>/dev/null)/latest.json"
[ -f "$DREAM_LATEST" ] && jq '.dream_job.deliverables[]? | select(.kind=="pr")' "$DREAM_LATEST"
```

Classify each PR with **`desk-merge`'s tier table** (low/high/mixed/unclear by files touched) and
follow its rule here too: **never merge from this skill.** Run or delegate `babysit` if CI is red
or there are conflicts; surface title/URL/tier/checks; point to `desk-merge` for the actual merge.
Include a Dream row when `subsystem/dream/latest.json` has `status` in `staged`/`merge_ready`.

```markdown
**Git** · instance: main @ origin · host: `feat/foo` 🟡 dirty · 2 open PRs

| PR | Tier | State | Next |
|----|------|-------|------|
| ennui #88 | low | mergeable ✅ | → desk-merge |
| ennui #12 | high | CI green | 🚧 diff before merge |

**Dream** · merge_ready · [ennui#42](…) — staged overnight · → desk-merge
```

Don't create worktrees without the owner asking — suggest the `git worktree add` command instead.

---

## Persist (soul)

When a run produces a durable conclusion about **secretary itself** (not owner business facts),
append to `soul.md`'s `## memory`:

```markdown
- **YYYY-MM-DD** — <one-line conclusion>
```

- Owner/business facts go to `desk-write` (wiki or module memory), not here.
- Don't rewrite `purpose`, `objectives`, or `alignment` during a normal run — only append to
  `memory`. Structured soul evolution belongs to `desk-dream`.
- No commit unless the owner asks.
- Cap at ~20 recent bullets; prune only on explicit soul review.

If the Align step found **both** or **conflict**, include a one-line `Align` row in the report.

---

## Report

Inline, compact (`rules/sec-output.md`). Header: `desk-drone — <topic> · <host-slug>`

```markdown
desk-drone — CLab negotiation · ennui

**Zone** · `ennui` on `feat/negotiation` · 🟡 4 uncommitted · WIP: `tipo:estable` mentoría

**Memory** (recall)

| | Field | Value |
|---|---|---|
| 🏢 | Org | ChangeLab — active negotiation on scope/fees · `wiki:organizaciones/changelab` |
| 👤 | Contact | Juliana — last met today 14:00 · `meetings:2026-07-02` ⏳ tentative PR #412 |
| 🧵 | Open thread | Counter-proposal pending their legal review · `mail:2026-07-01` |

**Scan** · meeting ⏳ unmerged · mail ✅ · contract_health ok

**Align** · owner lane: client delivery (ennui) · secretary: obj-freshness + obj-blockers · both apply — merging PR #412 also closes a stale gap

**Gaps** · Juliana call summary not on `main` yet (PR #412). Legal reply not in mail memory.

**→ Next** · `desk-compose` — draft follow-up to Juliana anchoring today's call · or `pr-sync` if continuing PR #88

> Ready to route — which path?
```

Rules: one screen max before the `→` line; tables only for ≥3 comparable fields. Omit empty
sections (unlike `desk-overview`/`desk-refresh` — this is a short orientation, not a full sweep). Don't dump
raw file contents — cite with `` `source:date` ``. Autonomous steps leave `📎 _secretary scanned —
<host> · <topic>_` (tier 🫧, per haptics doctrine).

---

## Automatic vs requires OK

| Action | Automatic | Requires OK |
|---|---|---|
| `git fetch` instance | ✅ | |
| `secretary fresh` / `recall` | ✅ | |
| Read host repo / wip / heartbeat / soul | ✅ | |
| Append soul `memory` | ✅ | owner asks to commit |
| `desk-meeting` probe (read Tactiq) | ✅ | |
| Trigger `reuniones-update` / pipeline | | 🚧 offer |
| `desk-refresh` full repair | | suggest |
| Send mail / merge / Drive mutate | | 🚧 |
| Merge a PR (via `desk-merge`) | | 🚧 — surface only |
| Commit on instance | | owner asks |

---

## When to use / not use

- **Use:** any repo, topic-driven work needing secretary memory; entering Cowork for a
  negotiation, person, or project; "what do we know about X" from a client repo; meeting just
  ended and work continues elsewhere.
- **Not:** full disconnect repair → `desk-refresh`; daily brief progress → `desk-overview`; raw WIP only →
  `desk-state`; send Cursor a task → `to-cursor` (this skill may route there after orienting).

## Do not

- Run the full five-phase `desk-refresh` by default.
- Replace child skills — always delegate execution.
- Assume `cwd` is the secretary instance, or auto-merge a PR.
- Create or duplicate the daily brief issue.
- Wait passively for the owner to ask about freshness.
