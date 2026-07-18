---
name: secretary-briefing
description: >-
  Morning Secretary briefing — synthesize in-flight work, team reports, and create or refresh the
  daily agenda GitHub Issue for the owner. Instance config: operational/briefing.md.
---

# secretary-briefing — daily agenda issue

Read instance `CLAUDE.md` at `SECRETARY_INSTANCE` before starting. Instance appendix:
`operational/briefing.md` (accounts, calendar, labels, presentation rules).

Doctrine: `rules/skills-contract.md`

## Instance setup

```bash
CFG=$(secretary config show)
export SECRETARY_INSTANCE="${SECRETARY_INSTANCE:-$(echo "$CFG" | jq -r .instance)}"
TIMEZONE=$(echo "$CFG" | jq -r '.timezone // "UTC"')
TODAY=$(TZ="$TIMEZONE" date '+%Y-%m-%d')
DOW=$(TZ="$TIMEZONE" date '+%A')
BRIEF_REPO=$(echo "$CFG" | jq -r '.brief.repo // empty')
BRIEF_LABEL=$(echo "$CFG" | jq -r '.brief.label // "tipo:informe-diario"')
PERSONAL_ACCOUNT=$(echo "$CFG" | jq -r '.accounts.personal // empty')
WORK_ACCOUNT=$(echo "$CFG" | jq -r '.accounts.Company // .accounts.work // empty')
BRIEF_REFRESH_ISSUE="${BRIEF_REFRESH_ISSUE:-}"
export BRIEF_ASSIGNEE="${BRIEF_ASSIGNEE:-yourusername}"   # owner login — see table below

if [ -z "$BRIEF_REPO" ]; then
  BRIEF_REPO=$(gh -R "$SECRETARY_INSTANCE" repo view --json nameWithOwner -q .nameWithOwner)
fi
```

If `subsystem/heartbeat/latest.md` exists, read it first for deltas, acc↔git match, and operational
state (avoids full rescan when heartbeat already consolidated).

Heartbeat rules: `run-routine.sh` runs `pre-brief-pipeline.sh` before this routine unless
`PRE_BRIEF_SKIP_PIPELINE=1`. Catch-up after downtime: `PRE_BRIEF_FORCE=1`. Prefer pre-brief
heartbeat; else most recent `<= 07:45` local; else full sweep with explicit "pre-brief heartbeat
absent" note.

Absorb `loose-*` match rows per spec 008 autonomy tiers (`operational/briefing.md`).

---

## Refresh mode (`BRIEF_REFRESH_ISSUE`)

When invoker exports `BRIEF_REFRESH_ISSUE=<n>` (e.g. `sec-refresh` Phase 5), **edit** the existing
issue — idempotent same-day refresh.

**Validate at start:**

```bash
if [[ -n "$BRIEF_REFRESH_ISSUE" ]]; then
  gh issue view "$BRIEF_REFRESH_ISSUE" --repo "$BRIEF_REPO" \
    --json number,title,state,labels \
    --jq "if ([.labels[].name] | index(\"$BRIEF_LABEL\")) then . else error(\"issue missing $BRIEF_LABEL\") end"
fi
```

| Step | Normal | Refresh |
|------|--------|---------|
| Phase 0 step 4 — close previous | Close `#PREV`, link to new | **Skip** |
| Phase 6 delivery | `gh issue create` | `gh issue edit $BRIEF_REFRESH_ISSUE` |
| Post-delivery comment | — | Refresh comment (preserve sec-status) |

Without `BRIEF_REFRESH_ISSUE` → create new issue (normal mode).

---

## Phase 0 — Read, carry over, close previous brief

Daily brief is a handoff, not an accumulating file.

```bash
PREV_ISSUES=$(gh issue list --repo "$BRIEF_REPO" --label "$BRIEF_LABEL" --state all \
  --json number,title,createdAt,state \
  --jq 'sort_by(.createdAt) | reverse | .[0:3] | map(.number)')
PREV=$(echo "$PREV_ISSUES" | jq '.[0]')
```

1. **Read** last 3 briefs: owner comments, unchecked `- [ ]` items, **sec-status** comments (see
   `operational/briefing.md`).
2. **Advance what you can now** (Phase 0.7 tiers 0–2). No third-party sends or remote Drive mutation.
3. **Carry** what you cannot: unchecked items, decisions needed → today's issue.
4. **Close previous** with link to new — **unless refresh mode**.

```bash
if [[ -z "$BRIEF_REFRESH_ISSUE" ]]; then
  gh issue comment "$PREV" --repo "$BRIEF_REPO" --body "$(~/.claude/scripts/sec-signature.sh secretary-briefing --mark)
Closing this brief. Open items moved to #<NEW>.

---
$(~/.claude/scripts/sec-signature.sh secretary-briefing --footer)"
  gh issue close "$PREV" --repo "$BRIEF_REPO"
fi
```

---

## Phase 0.5 — Reconcile mail carry-over

`revision-correo` runs **18:00** local. Morning brief uses **previous evening** batch as primary mail
source. Before carrying mail-sending items, verify resolution:

```bash
git -C "$SECRETARY_INSTANCE" fetch origin --quiet
git -C "$SECRETARY_INSTANCE" show origin/main:extractors/mail/state.md
gh pr list --repo "$BRIEF_REPO" --state merged --search "correo/auto-" --limit 5 \
  --json number,title,mergedAt,headRefName
# Optional: gog gmail search 'in:sent newer_than:3d' on PERSONAL_ACCOUNT
```

Match in any source → report as `entregado`; do not carry as pending. Partial match → carry with
precise note. See `operational/briefing.md` for staleness note before 18:00.

---

## Phase 0.7 — Autonomy tiers (heartbeat + inputs)

Spec: `_diseño/specs/008-sec-heartbeat/spec.md`. Tier table in `operational/briefing.md`.

| Tier | Autonomy | Gate |
|------|----------|------|
| 0 | Reconciliation, carry-over | — |
| 1 | Email drafts (no send) | 🚧 send |
| 2 | Docs, Drive drafts, email with ready links | no send/remote mutation |
| 3 | Multi-step flows | 🚧 per item |
| 4 | Business decision, third-party send | 🚧 always — list only |

Per `loose-acc`: classify tier, execute ≤1 when inputs suffice, carry ≥3 with 🚧.
Per `loose-git`: add **🧵 Trabajo en marcha** row; evaluate Phase 2.6 if allowlisted.

---

## Phase 1 — In-flight work

Scan `dispatch.executor.repos` from config **plus** brief repo (`$BRIEF_REPO`).

Single unified table: Repo · Branch · PR · Situación · Relation and next step.

**Repo column:** slug only by default (`operational/briefing.md`). `gh` commands use full `owner/repo`.

**Situación values:** `en curso` | `recién mergeado` | `necesita empuje` (stale rules: manual PR >3d,
auto-extractor >1d).

Sources:

```bash
gh pr list --repo "$BRIEF_REPO" --state open --json number,title,headRefName,isDraft,reviewDecision,url,updatedAt
# Repeat per allowlist repo; merged last 3–7 days; local worktrees when paths exist
```

---

## Phase 1b — Team reports

Feeds **📋 Resumen de la corrida** (end of brief, not top).

List auto PRs (`correo|reuniones|whatsapp|wiki|housekeeping|job-search|drive)/auto-*`) last 24h on
brief repo. Extract **Resumen** section from each PR body. Classify ✅ merged / ⏳ open / ⚠️ CI red.

---

## Phase 2 — Due or upcoming actions

Model: `_diseño/specs/007-modelo-acciones/`. Source:

```bash
ACTIONS=$(secretary config path meetings.memory)/acciones.md
THIS_MONTH=$(TZ="$TIMEZONE" date '+%Y-%m')
grep -nE "deadline: ($THIS_MONTH|…)" "$ACTIONS" | head -40
```

**Filter for "Tu lista para hoy":** `estado ∈ {abierta, en-curso}`, `dueño ∈ {mía, compartida}`,
`tipo = compromiso`. Route `tercero`/`seguimiento` → **⏳ Esperando a otros**; `idea` → parking.

### Phase 2.1 — Scheduling vs calendar

See `operational/briefing.md` § Calendar reconciliation. Conservative match only.

### Phase 2.5 — Job applications (weekdays)

See `operational/briefing.md` § Job applications. Read-only `loops/job-search/applications.md`.

### Phase 2.6 — Executable dispatch (low risk)

Allowlist: `dispatch.executor.repos`. Skip if empty. **All** criteria required; max 3/run; idempotent
by `acc-id` search. Create issue + `dispatch:execute` label. Conservative — when in doubt, candidate
not auto-dispatch. Details in instance `CLAUDE.md` § dispatch.

---

## Phase 3 — Open `para-User` issues

```bash
gh issue list --repo "$BRIEF_REPO" --label "para-User" --state open \
  --json number,title,createdAt,url
```

---

## Phase 6 — Deliver issue

**Refresh:** `gh issue edit` + refresh comment (see refresh mode).

**Normal:**

```bash
gh issue create \
  --repo "$BRIEF_REPO" \
  --title "📋 Briefing — $TODAY ($DOW)" \
  --label "$BRIEF_LABEL" \
  --assignee "$BRIEF_ASSIGNEE" \
  --body "$BODY"
```

### Body structure (template v2.1)

Load: `secretary config path templates` → `brief-body.md`. Required sections:

1. `## ✅ Tu lista para hoy`
2. `## 🧵 Trabajo en marcha`
3. `## ⏳ Esperando a otros`
4. `## 🤖 Secretary — despacho y entregas`
5. `## 📋 Resumen de la corrida` + `### Reportes del equipo`

Signature: harness `sec-signature.sh secretary-briefing --mark` / `--footer`.

---

## Restrictions

- No PRs or merges.
- No third-party sends.
- Read-only on `SECRETARY_INSTANCE` tree.
- External outputs: brief issue + allowlist `dispatch:execute` issues (Phase 2.6, conservative).
- Create issue even when no alerts.
