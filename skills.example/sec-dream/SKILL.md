---
name: sec-dream
description: >-
  Overnight / on-demand completion loop — one substantial dream job per run: cross-signal synthesis
  from meetings, mail, and repo WIP into a staged deliverable (PR and/or Gmail draft). Consolidates
  memory as input, reports in subsystem/dream/. Triggers: "/sec-dream", "/sec-dream soul",
  "/sec-dream --job <lane>", scheduled headless 05:00 America/Lima (budget 120 min).
user-invocable: true
---

# sec-dream — overnight completion

**Mission:** finish **one** stalled owner lane overnight (or on demand) by crossing the latest signals
(meeting, mail, repo), synthesizing a real deliverable, staging it merge-ready, and reporting durable
artifacts for `sec-drone`, `pulse`, and optional briefing embed. Memory consolidation is **input** for
the job — not the headline output.

Doctrine: `rules/skills-contract.md` · Output: `rules/sec-output.md` · Spec: instance
`_diseño/specs/L5-observabilidad/020-sec-dream/spec.md`

## Principles

- **One job per run.** Max one primary `dream_job`; `deferred_queue` max 3 — no parallel suggestions.
- **Owner lanes first.** Harness hygiene informs scoring only — not the default primary job.
- **Cross-signal.** Prefer lanes with ≥2 independent sources (meeting, mail, repo, open PR, brief
  `sec-status`) within 7d pointing at the same deliverable.
- **Gates:** PR create/update OK · Gmail **draft** OK (`gog`) · **send never** · **merge never**
  (surface merge-ready; owner invokes `sec-merge` next session).
- **Decision B:** all soul/harness autonomous edits → **worktree → PR** — never direct push to `main`.
- **Forked context** for scheduled and default on-demand runs — not the routine default model.

## Model selection

Long-context, multi-step completion — distinct from heartbeat / light routine triage.

```bash
CFG=$(secretary config show)
DREAM_MODEL="${SECRETARY_DREAM_MODEL:-$(echo "$CFG" | jq -r '.dispatch.routines.dream_model // empty')}"
ROUTINE_MODEL=$(echo "$CFG" | jq -r '.dispatch.routines.model // empty')
```

| Source | Key |
|--------|-----|
| Env override | `SECRETARY_DREAM_MODEL` |
| Instance config | `dispatch.routines.dream_model` in `.secretary.yml` |
| Baseline only | `dispatch.routines.model` — document in log if used as emergency fallback |

**Degraded run:** if dream model unavailable or over cost ceiling → consolidate + update
`deferred_queue` + `dream_job.status: blocked` with reason in JSON/log — no silent switch to
expensive default without log entry.

**Pre-v1 live overnight:** model evaluation harness (spec FR-9) should gate production scheduled
runs; v1 ships collect + skill contract without requiring a live LLM overnight pass.

## Store (write destination)

```
$SECRETARY_INSTANCE/subsystem/dream/
├── latest.json
├── dream-YYYYMMDD.json
└── log/YYYY-MM-DD.md
```

Resolve: `secretary config path subsystem.dream` · Schema: `subsystem/dream/README.md`

Collect debug (gitignored): `subsystem/dream/collect/collect-*.json`

## Guardrails

| Action | Autonomous? |
|--------|-------------|
| Create/update PR (owner repo) | Yes — primary deliverable |
| Gmail draft (`gog`) | Yes |
| Gmail send / WhatsApp / third party | **Never** 🚧 |
| Merge PR | **Never** — `sec-merge` next session |
| Edit `knowledge/objectives/` body | **Never** — 💡 dispatch suggestion |
| Executable / workflow / `.secretary.yml` | **Never** 🚧 |
| Soul `memory` prune / harness typo | Fallback only — worktree → PR |
| Soul `purpose` / drone `objectives` | `--soul` → proposal until OK → PR |

## Triggers

| Mode | Invocation |
|------|------------|
| Scheduled | 05:00 instance timezone — finishes before portal aggregate (07:00), pre-brief heartbeat (07:10), and briefing |
| On-demand | `/sec-dream` |
| Soul review | `/sec-dream soul` |
| Force lane | `/sec-dream --job <lane>` |
| Consolidate only | `/sec-dream --consolidate-only` |

Indirect: portal (spec 019) · `pulse` reads `latest.json`

---

## Skill chain

| Need | Delegate |
|------|----------|
| Deterministic gather | `scripts/dream/collect.py` |
| Wiki pending integrate | `sec-sys-integrate` (Consolidate phase) |
| Memory dedupe | `sec-consolidate` (when backlog) |
| PR hygiene on dream job PR | `babysit` (Stage phase, job worktree) |
| Next-session merge | route note → `sec-drone` → owner `sec-merge` |
| Mail draft deliverable | `gog` draft (never send) |
| Fundamental soul edit | `--soul` proposal → owner OK → PR |

---

## Procedure — phases 0–5

### Instance setup

```bash
CFG=$(secretary config show)
export SECRETARY_INSTANCE="${SECRETARY_INSTANCE:-$(echo "$CFG" | jq -r .instance)}"
export SECRETARY_CORE="${SECRETARY_CORE:-$(echo "$CFG" | jq -r .core)}"
TIMEZONE=$(echo "$CFG" | jq -r '.timezone // "UTC"')
TODAY=$(TZ="$TIMEZONE" date '+%Y-%m-%d')
DREAM_ROOT=$(secretary config path subsystem.dream)
DREAM_MODEL="${SECRETARY_DREAM_MODEL:-$(echo "$CFG" | jq -r '.dispatch.routines.dream_model // "dream"')}"
OBJECTIVES_ROOT=$(secretary config path knowledge.objectives.root 2>/dev/null || echo "")
DRONE_SOUL=$(secretary config path subsystem.drone)/soul.md
git -C "$SECRETARY_INSTANCE" fetch origin -q
```

### Phase 0 — Aggregate

Reuse portal aggregate when fresh (<30m):

```bash
PORTAL_LIVE="$SECRETARY_INSTANCE/subsystem/portal/live-data.json"
# If missing or stale → skip; heartbeat/collect still run in Phase 1
```

Read `subsystem/heartbeat/latest.md` for loose-git / acc↔git context (input to scoring, not output).

### Phase 1 — Discover + Gather

**Deterministic collect** (required):

```bash
python3 "$SECRETARY_INSTANCE/scripts/dream/collect.py" --write-collect
# Or stdout only:
python3 "$SECRETARY_INSTANCE/scripts/dream/collect.py" --format json
```

Buckets: objectives lanes · heartbeat summary · soul memory recent · module memory paths · open PRs
on dispatch allowlist · brief `sec-status` · `contract_health` · `validate_status` ·
`job_candidates[]` with cross-signal score hints.

**Discover (LLM + rules):**

1. Read `job_candidates` from collect output — top row is a hint, not automatic selection.
2. Apply FR-4–FR-7: require ≥2 source types for primary job unless `--job <lane>` forces owner intent.
3. Pick **one** primary `dream_job` or set `skipped_no_owner_job` with reason.
4. Populate `deferred_queue` (max 3) from remaining scored lanes — not executed this run.
5. Every `signal` must cite a resolvable path or `gh` ref — no hallucinated lanes.

**Gather (cross-medium):** for the chosen lane, read fresh evidence:

- Meetings: `extractors/meetings/summaries/`, unmerged `reuniones/auto-*` PRs
- Mail: `extractors/mail/memory/`, stale draft hints via `sec-mail` step 0 if needed
- Repo WIP: host path from `dispatch.executor.repos` for the lane (worktree for edits in Phase 3)

### Phase 2 — Consolidate

Input processing **for the chosen job** — not a standalone deliverable.

When wiki `sec:pending` backlog or module memory noise detected:

1. Invoke `sec-sys-integrate` (wiki annotations) and/or `sec-consolidate` (dedupe).
2. Record actions in JSON `consolidation` block — e.g. `"wiki_integrate": "invoked"`.
3. Do **not** present consolidation as the primary human outcome if a `dream_job` completes.

### Phase 3 — Synthesize + Stage

**Synthesize (dream model):** produce deliverable content — doc, contract terms, structured markdown,
Gmail draft body, etc. Use consolidated + gathered signals only.

**Stage (worktree in target repo):**

```bash
# Example pattern — expand repo path from dispatch allowlist
WT="$HOME/.wt/dream-${TODAY}-<lane>"
git worktree add -b "dream/<lane>-${TODAY}" "$WT" origin/main
cd "$WT"
# … edit deliverable files …
git add -A && git commit -m "feat(<scope>): dream job <short title>"
export SECRETARY_SKILL=sec-dream
export SECRETARY_BRANCH=$(git branch --show-current 2>/dev/null || true)
SIG_MARK=$(~/.claude/scripts/sec-signature.sh sec-dream --mark)
SIG_FOOT=$(~/.claude/scripts/sec-signature.sh sec-dream --footer)
gh pr create --title "…" --body "${SIG_MARK}

Closes dream job …

---
${SIG_FOOT}"
```

- Optional Gmail draft: `gog` — **draft only**, never send.
- Run **`babysit`** on the dream PR until merge-ready (CI green, no conflicts, human comments triaged).
- Set `dream_job.status` → `staged` | `merge_ready` | `blocked`.

**Canonical reference scenario (US-1 — CLab contract terms):**

| Signal | Source |
|--------|--------|
| Meeting | Latest CLab/Juliana transcript or summary in meetings memory |
| Mail | Stale Gmail draft thread on contract terms |
| Repo | Scattered term drafts in Cowork sideproject without integration |

**Dream job:** cross Jul 1 meeting terms → synthesize unified contract terms doc or mail draft →
open/update PR **merge-ready** in `cowork-sideproject` → `next_session`: `sec-drone` surface PR →
`sec-merge` tier-low if owner confirms.

### Phase 4 — Report

Write committed artifacts:

```bash
# dream-YYYYMMDD.json — full schema (see spec)
# latest.json — copy/symlink of today's canonical file
# log/YYYY-MM-DD.md — prose: job outcome, PR links, consolidation as footnote, next session steps
```

JSON must include exactly one primary `dream_job` or explicit `skipped_no_owner_job`.

`next_session` field example: `sec-drone surface PR → sec-merge tier-low if green`

Haptics (scheduled): `📎 _secretary dream — <lane> · <status>_` (tier 🫧)

### Phase 5 — Fallback

Run **only** when no owner `dream_job` selected, run blocked, or `--soul` invoked.

| Path | Action |
|------|--------|
| `--soul` | Produce `soul_proposal` markdown diff for `purpose` / drone `objectives` — apply only after 🚧 OK → worktree → PR |
| Soul/harness fallback | Max **one** PR: memory prune, audit link fix, harness doc typo — **worktree → PR always** (decision B) |
| No qualifying job | `dream_job.status: skipped_no_owner_job` + `deferred_queue` updated |

Never edit owner `knowledge/objectives/` body autonomously.

---

## Report (on-demand / session tail)

Header: `🌙 **sec-dream — <lane or skipped>** · <date>`

```markdown
🌙 **sec-dream — sideproject / CLab terms** · 2026-07-03

**Job** · merge_ready · `job-20260703-clab-terms`

| | Field | Value |
|---|---|---|
| 🧵 | Lane | sideproject |
| 📎 | PR | [cowork-sideproject#42](https://github.com/…/pull/42) · babysit green |
| ✉️ | Mail | draft hint — reply thread CLab (not sent) |
| 🔄 | Consolidation | 2 wiki annotations integrated (input) |

**Deferred** (max 3) · job-search · doc2struct — lower cross-signal score

**→ Next session** · `sec-drone` surface PR #42 → `sec-merge` tier-low on confirm
```

If fallback only: lead with `skipped_no_owner_job` or soul proposal — do not fake a primary job.

---

## Automatic vs requires OK

| Action | Automatic | Requires OK |
|--------|-----------|-------------|
| `collect.py` | ✅ | |
| Job selection (LLM) | ✅ | `--job` forces lane |
| `sec-sys-integrate` / `sec-consolidate` | ✅ when backlog | |
| Open/update PR in owner repo | ✅ | |
| Gmail draft | ✅ | |
| Gmail send | | 🚧 never |
| Merge PR | | 🚧 never — sec-merge |
| Soul `purpose` / objectives apply | | 🚧 always |
| Dispatch issue creation | | 🚧 — draft in output only |

---

## When to use / not use

- **Use:** overnight completion of one stalled owner lane; cross-signal synthesis after intense days;
  `/sec-dream soul` after strategic pivot.
- **Not:** daily agenda → `secretary-briefing`; in-session git ordering → `sec-drone`; deterministic
  snapshot → `sec-heartbeat`; ecosystem health sweep → `housekeeping`.

## Do not

- Run multiple parallel dream jobs or quantity targets (3–5 suggestions).
- Send mail or merge PRs autonomously.
- Push soul/harness edits directly to `main`.
- Replace `wiki-update` HTML build or full routine extractors.
