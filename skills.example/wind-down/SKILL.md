---
name: wind-down
description: >-
  End-of-session ritual that sweeps open loops and routes each to the skill that
  resolves it — loose ideas to offload, continuing threads to handover, code
  branches/PRs to push + draft PR (advanced to ready-for-review when nothing of
  yours blocks). Continuity prompts via jump (two-line fallback if jump is
  missing). Refreshes status on touched docs/plans nodes. Triggers: "/wind-down",
  "let's wrap up", "close this". NOT for mid-session ideas, mid-session
  continuations without closing, standalone handover, or memory consolidation.
user-invocable: true
---

# wind-down — end-of-session ritual

Orchestrator, not executor. Detects open loops from the current session, routes
each to the resolving skill, reports in tables. No coaching, no nagging.

Doctrine: `rules/skills-contract.md` · related issues doctrine · GitHub signatures

## Instance setup

```bash
CFG=$(secretary config show)
export SECRETARY_INSTANCE="${SECRETARY_INSTANCE:-$(echo "$CFG" | jq -r .instance)}"
BRIEF_REPO=$(echo "$CFG" | jq -r '.brief.repo // empty')
```

Workspace/repo routing for handover destinations and offload context: **instance
`CLAUDE.md`** (Cowork/Dev layout, client map). Do not embed absolute cwd tables.

## Principles

- **No nagging.** Never close with reproach about unpushed commits. Each loop is
  resolved (signal created) or parked (logged decision).
- **Advance, don't park by default.** Session PRs should not sit in draft by
  inertia. Push as far as possible without owner input — push, draft PR if
  missing, update body if drifted, mark ready when nothing of yours blocks.
  Owner-dependent items become named blockers.
- **Close the loop to merge — tier-gated.** For each mergeable session PR,
  classify tier by touched files:
  - **Low tier** (data/prose only: `*.md`, `*/memory/`, `wiki/`, summaries,
    notes): folds into the **single Stage 2 confirmation**.
  - **High tier** (executable: code, `.github/`, `package.json`, instance YAML,
    build scripts): **never** fold into blanket Y. Show diff/summary and ask a
    dedicated question before merge.
  - **Mixed → high wins. Unclear → high.** Block merge on conflicts, unresolved
    human comments, or code-failure CI. When CI is infra-blocked, local validation
    on PR head may satisfy the gate (same suite as merge skill). Run babysit first
    for conflicts, human comments, or real test failures.
- **Capture, don't execute.** Loose ideas → offload, not implementation now.
- **One sweep, one checklist, one confirmation.** Pre-resolve sub-skill inputs.
- **"I don't know" parks.** Log open questions and continue.
- **Session scope only.** Unrelated pre-existing dirt: mention once, no action.
- **Refresh heartbeat before exit.** If close changed material state, run
  heartbeat with **commit+push to `main`** when instance policy requires it.

## Skill chain

| Loop | Routes to | Friction reduction |
|------|-----------|-------------------|
| Loose idea | offload (blob or with-context) | One idea = one restart unit |
| Thread continues elsewhere | handover + resume | Pre-fill title and destination |
| Durable knowledge | offload (wiki vs issue triage) | Do not write wiki directly |
| Project milestone / deliverable | `sec-write` (wiki theme) | One-line dated fact pending integrate |
| Harness / system friction | `sec-learn` → offload (default ISSUE) | Not wiki facts |
| Branch / PR from session | push → PR → ready → **tier merge** | Low → merge in single Y; high → ask |
| Chat-reported progress not persisted | `secretary status` | Sweep before close |
| Memory consolidation | `sec-consolidate` | Only if explicit |
| Open PR with unread comments | mention sync next session | Park, don't sync now |
| Project hygiene | `sec-project-sync` | AGENTS.md, scratch, layout, entity-contract drift |
| Continuity prompts | **jump** | Archetypes + tiers; owner picks; optional offload |
| Active work plan | `docs/plans/<slug>.md` | Append node status + Log for nodes touched this session |

When calling handover, pre-fill inputs from Stage 1 — no re-interrogation.

## Procedure — two stages (Proposal & Close)

Ultra-compact bullets with decision traffic lights. **Zero boilerplate:** omit empty
sections.

### Stage 1 — Proposal

Scan repos touched, loose ideas, handovers, milestones, friction:

```bash
git -C <repo> status -sb
git -C <repo> branch --show-current
git -C <repo> log --oneline @{u}..HEAD
gh pr list --repo <owner/repo> --head <branch>
```

**Issues touched this session.** If the session closed, commented substantially on,
or merged a PR resolving an issue, run bidirectional related-issues check before
reporting.

**Project sync (Cowork/Dev).** Run project sync for AGENTS.md, scratch purge, layout,
entity-contract / EDT drift.

**Work plan status.** If `docs/plans/` has an `active` plan (or `plan_ref` in session):
for each node touched this session, propose status updates (`running`→`done` /
`blocked`) and Log rows. Do **not** reshape the graph without owner OK.

**Continuity (jump).** If the session produced material work, run jump (scan →
archetype table → owner picks → emit prompts). Do not reimplement prompt generation.

**Fallback** if jump is missing or there was no material work — two lines only:

```
Continuity: local handover in .cursor/tasks/ <or> none.
Open issues: <list or none>.
```

**Status sweep (blocking).** Persist chat-reported progress not yet recorded
(`secretary status`).

#### Stage 1 template

Render only sections with items:

````markdown
## Close proposal

### Code and PRs
- 🟢 **<repo>** (`<branch>`): <N> commits unpushed → push + draft PR
- 🟢 **<repo>** (PR #<N>, `.md` only): low-tier → push + ready + squash merge
- 🔴 **<repo>** (PR #<N>, executable): high-tier → merge with squash? (Recommended: Y)

### Memory and milestones
- 🟡 **<topic>**: <milestone> → note in wiki theme? (Recommended: Y)
- 🟡 **harness**: `<friction>` → record via sec-learn? (Recommended: N)
- 🟢 **durable knowledge**: `<fact>` → offload → wiki

### Work plan
- 🟢 **<plan_ref> node <id>**: <pending status change> → append Log

### Continuity
- 🟢 **<thread>**: jump → <archetype> / tier <surgical|operational|autonomous>
- 🟢 **loose idea**: `<idea>` → offload blob
- 🟢 **no material**: fallback — local handover or open issues

---

**Shortcuts:**
- **`1` / `All`** — execute recommended (🟢, accept 🟡 milestones, merge 🔴 after ask)
- **`2` / `Code only`** — push/PRs only
- **`3` / `Minimum`** — WIP commit + local handover, no remote

**Or adjust:**
```text
<repo> (merge PR #<N>): Y
<topic> (wiki milestone): Y
harness (sec-learn): N
plan node <id>: done
```
````

### Stage 2 — Execution & close report

Hard rules: Conventional Commits per instance `CLAUDE.md`. Never force-push. Never
push code to `main` without a branch. On failure, park as issue and continue.

**GitHub signature (mandatory)** before any `gh pr create`, `gh issue create`, or
`gh issue comment` this skill emits — use the instance signature helper with skill
name `wind-down`.

**Main checkout gate (blocking)** before declaring close or heartbeat, when instance
policy requires the secretary checkout on `main` clean except heartbeat / untracked.

If Stage 2 produced material changes → heartbeat once per instance policy; note in close.

#### Stage 2 template

```markdown
## Session closed

### Code and PRs
- ✅ **<repo>**: branch `<branch>` pushed; PR #<N> created / squash-merged

### Memory and milestones
- ✅ **<topic>**: milestone noted
- ⏸️ **harness**: skipped by owner

### Work plan
- ✅ **<plan_ref>**: nodes <ids> status + Log updated
- ⏸️ **plan**: none active

### Continuity
- ✅ **jump**: prompts in chat and/or `.cursor/tasks/<date>-<slug>.md`
- ⏸️ **jump**: fallback
- ✅ **heartbeat**: updated

Done.
```

## When to use / not use

- **Use:** explicit close intent
- **Not:** mid-session idea → offload; mid-session continuations without closing →
  jump; harness learning mid-session → `sec-learn`; standalone handover; consolidation

## Don't

- Nag, leave PRs in draft by inertia, fold high-tier merge into blanket Y,
  reimplement capture, implement loose ideas, touch unrelated repos, force-push,
  or write motivational closes
- Route harness friction to wiki by default — Stage 1 harness row → `sec-learn` on Y
- Reshape `docs/plans` graphs without owner OK — status + Log only
