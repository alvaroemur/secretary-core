---
name: wind-down
metadata:
  close-contract: "3"
description: >-
  End-of-session ritual that sweeps open loops and routes each to the skill that
  resolves it — loose ideas to offload, continuing threads to handover, each
  code topic to its own worktree and a PR ready to integrate, with a merge
  proposal when the change is clear or verifiable. Reports related open work and
  co-changes. Continuity prompts via jump (two-line fallback if jump is
  missing). Refreshes status on touched docs/plans nodes. Triggers: "/wind-down",
  "let's wrap up", "close this". NOT for mid-session ideas, mid-session
  continuations without closing, standalone handover, or memory consolidation.
user-invocable: true
---

# wind-down — end-of-session ritual

Orchestrator, not executor. Detects open loops from the current session, routes
each to the resolving skill, reports in tables. No coaching, no nagging.

Doctrine: `rules/skills-contract.md` · related issues doctrine · GitHub signatures ·
instance git policy `canon/rules/git/` (`integracion.md`: worktrees, ready to integrate, merge)

## Shared close context

Collect session state once. Identify the repos and files touched by this session; do not infer them from the last commit. State uncertainty rather than attributing another session's edits to this one. Act only on this session's work; other work is read, never changed (see **Related work sweep**).

Build one `close_context`: session id, actual checkout, branch, commit, touched files and their status, decisions and reasons, result, blockers, next action, PR, references, and one brief path. Query the branch PR and unpublished commits once. No auxiliary session or reflection agent is needed.

Pass this object to project sync, handover and jump. They reuse it instead of repeating git or conversation collection. Handover is the only brief writer; jump uses that brief. Keep Cowork/Dev briefs in the actual checkout's `.briefs/`, never in the instance brief tree.

### Related work sweep (read-only)

For each repo touched, read once and **report, never act**:

```bash
git -C <repo> worktree list --porcelain
gh pr list --repo <owner/repo> --state open --json number,title,headRefName,files
gh issue list --repo <owner/repo> --state open --json number,title,labels
```

Relate an item when it touches the same files or the same scope (`<type>(<scope>)`, `hilo:` label). List it as **close before** (it blocks or conflicts with this change: same files, a dependency PR) or **related** (same topic, no conflict). For each other worktree, add whether it is integrated: `git merge-base --is-ancestor <branch> origin/main`.

### Co-changes (what this change drags along)

1. **References:** search the touched file names, skill names and changed identifiers in `AGENTS.md`, `CLAUDE.md`, `README*`, `docs/`, `tests/`, rules and the instance policy (`rg -l '<name>'`). Any hit not updated in this session is a co-change candidate.
2. **Installed copies:** when skills or playbooks changed, compare the hash of each installed copy with the versioned source (`shasum`). A mismatch means a redeploy is pending.

Report co-changes as rows; do not edit outside this session's topic without the owner's OK.

An optional `secretary efficiency close-snapshot` can supply mechanical git state when available. It is not required: normal git tools and the current conversation suffice. Do not install a runtime to close a session.

## Instance setup

```bash
CFG=$(secretary config show)
export SECRETARY_INSTANCE="${SECRETARY_INSTANCE:-$(echo "$CFG" | jq -r .instance)}"
BRIEF_REPO=$(echo "$CFG" | jq -r '.brief.repo // empty')
```

Workspace/repo routing for handover destinations and offload context: **instance
`AGENTS.md`** (Cowork/Dev layout, client map). Do not embed absolute cwd tables.

## Principles

- **No nagging.** Never close with reproach about unpushed commits. Each loop is
  resolved (signal created) or parked (logged decision).
- **One topic, one worktree, one PR.** Code and Cowork-management repos: each
  topic lives in `<repo>/.wt/<branch with "/" → "-">`, on a branch cut from
  `origin/main`, with one PR. The main checkout stays on a clean `main`. The
  instance repo keeps direct commits to `main`, but must end clean and pushed.
- **Ready to integrate is the close target.** Push as far as possible without
  owner input: commit, push, open the PR (not draft), update the body if it
  drifted. A topic is **ready** when the PR is open and not draft, `mergeable`
  is clean, CI is green (or the repo has no required checks) and human review
  comments are resolved. Anything missing becomes a named blocker.
- **Propose merge only when it is clear or verifiable.** Propose merging a ready
  PR when the change is **clear** (prose only, or code covered by tests that pass
  on the PR head) or **verifiable** — give a 1–3 step guide under 2 minutes:
  command + expected result, or what to look at in the diff. Otherwise say what
  is missing. Tier still applies: **low tier** (`*.md`, `*/memory/`, `wiki/`,
  notes) may fold into the single Stage 2 confirmation; **high tier** (code,
  `.github/`, `package.json`, instance YAML, build scripts; mixed or unclear →
  high) needs its own question with a diff summary. The merge itself runs
  through `desk-merge` (merge commit, never squash). Before proposing, check the
  repo allows it: `gh api repos/<owner/repo> -q .allow_merge_commit`.
- **Capture, don't execute.** Loose ideas → offload, not implementation now.
- **One sweep, one checklist, one confirmation.** Pre-resolve sub-skill inputs.
- **"I don't know" parks.** Log open questions and continue.
- **Act on session scope; read related work.** Unrelated pre-existing dirt: mention once, no action.
- **Refresh desk-heartbeat before exit.** If close changed material state, run
  desk-heartbeat with **commit+push to `main`** when instance policy requires it.

## Skill chain

| Loop | Routes to | Friction reduction |
|------|-----------|-------------------|
| Loose idea | offload (blob or with-context) | One idea = one restart unit |
| Thread continues elsewhere | handover + resume | Pre-fill title and destination |
| Durable knowledge | offload (wiki vs issue triage) | Do not write wiki directly |
| Project milestone / deliverable | `desk-write` (wiki theme) | One-line dated fact pending integrate |
| Harness / system friction | `desk-learn` → offload (default ISSUE) | Not wiki facts |
| Branch / PR from session | worktree check → push → PR → ready → **merge proposal** | Clear/verifiable only; merge via desk-merge |
| Related open work / co-changes | **report** (read-only sweep) | Close-before vs related; no action |
| Chat-reported progress not persisted | `secretary status` | Sweep before close |
| Memory consolidation | `desk-consolidate` | Only if explicit |
| Open PR with unread comments | mention sync next session | Park, don't sync now |
| Project hygiene | `desk-project-sync` | AGENTS.md, scratch, layout, entity-contract drift |
| Continuity prompts | **jump** | Archetypes + tiers; owner picks; optional offload |
| Active work plan | `docs/plans/<slug>.md` or `_diseño/plans/<slug>.md` | Append node status + Log for nodes touched this session |

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

**Worktree check (correct, then report).** For each topic touched this session:

```bash
git -C <checkout> rev-parse --show-toplevel   # folder
git -C <checkout> branch --show-current       # branch
git -C <repo> worktree list --porcelain
```

Expected: folder `<repo>/.wt/<branch-slug>` (slug = branch with `/` → `-`), branch
`<scope>/<desc>`, and the main checkout on a clean `main`. Correct mechanically and
report each move:

- Folder name ≠ branch, created by hand → `git worktree move <old> <repo>/.wt/<branch-slug>`.
- Branch `claude/*`, `codex/*` or another harness prefix → `git branch -m <scope>/<desc>` before the PR.
- Topic work on the main checkout → commit on a topic branch, `git switch main` in the main
  checkout, `git worktree add <repo>/.wt/<branch-slug> <branch>`.
- Worktree managed by a harness (under `.claude/worktrees`, `~/.codex/worktrees`,
  `~/.cursor/worktrees`) → do **not** move it: commit + push, `git switch --detach` there,
  then `git worktree add <repo>/.wt/<branch-slug> <branch>`.

Stop on that topic only (report, propose the command) when another live session uses the
folder, there are uncommitted changes not from this session, or the destination exists.

**Issues touched this session.** If the session closed, commented substantially on,
or merged a PR resolving an issue, run bidirectional related-issues check before
reporting.

**Project sync (Cowork/Dev).** Run project sync for AGENTS.md, scratch purge, layout,
entity-contract / EDT drift.

**Work plan status.** If `docs/plans/` or `_diseño/plans/` has an `active` plan
(or `plan_ref` in session): for each node touched this session, propose status
updates (`running`→`done` / `blocked`) and Log rows. Do **not** reshape the graph
without owner OK.

**Continuity (jump).** If the session produced material work, run jump (scan →
archetype table → owner picks → emit prompts). Do not reimplement prompt generation.

**Fallback** if jump is missing or there was no material work — two lines only:

```
Continuity: local handover in <session-cwd>/.briefs/ <or> none.
Open issues: <list or none>.
```

**Status sweep (blocking).** Persist chat-reported progress not yet recorded
(`secretary status`).

#### Stage 1 template

Render only sections with items:

````markdown
## Close proposal

### Code and PRs
- 🟢 **<repo>** (`<branch>`): <N> commits unpushed → push + PR (not draft)
- 🟢 **<repo>** worktree `<folder>` ≠ `<branch>` → `git worktree move` to `.wt/<branch-slug>`
- 🟢 **<repo>** (PR #<N>, `.md` only, ready): low-tier, clear → merge commit via desk-merge
- 🔴 **<repo>** (PR #<N>, executable, ready): high-tier → merge? Verify: `<command>` → `<expected>` (Recommended: Y)
- 🟡 **<repo>** (PR #<N>): not ready — missing `<CI | review | conflicts>`

### Related work and co-changes
- 🟠 **close before**: PR #<N> / `<worktree>` (`<branch>`, integrated: no) — touches `<files>`
- ⚪ **related**: issue #<N> — same scope `<scope>`
- 🟡 **co-change**: `<file>` mentions `<identifier>` → update in this PR? (Recommended: Y)
- 🟡 **redeploy**: installed `<skill>` hash ≠ source

### Memory and milestones
- 🟡 **<topic>**: <milestone> → note in wiki theme? (Recommended: Y)
- 🟡 **harness**: `<friction>` → record via desk-learn? (Recommended: N)
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
harness (desk-learn): N
plan node <id>: done
```
````

### Stage 2 — Execution & close report

Hard rules: Conventional Commits per instance `AGENTS.md`. Never force-push. Never
push code to `main` without a branch. On failure, park as issue and continue.

**GitHub signature (mandatory)** before any `gh pr create`, `gh issue create`, or
`gh issue comment` this skill emits — prefer `secretary signature wind-down
--runtime <actual-runtime>` (or its `--mark` / `--footer` outputs). When the CLI
is unavailable, use the configured instance helper and verify its runtime label.
Do not install a helper during close or claim another harness as the author.

**Main checkout gate (blocking)** before declaring close or desk-heartbeat, when instance
policy requires the secretary checkout on `main` clean except desk-heartbeat / untracked.

If Stage 2 produced material changes → desk-heartbeat once per instance policy; note in close.

#### Stage 2 template

```markdown
## Session closed

### Worktrees
| Worktree | Branch | PR | Missing |
|---|---|---|---|
| `<repo>/.wt/<branch-slug>` | `<branch>` | #<N> | nothing / CI / review / merge decision |

### Code and PRs
- ✅ **<repo>**: branch `<branch>` pushed; PR #<N> ready / merged (merge commit)

### Memory and milestones
- ✅ **<topic>**: milestone noted
- ⏸️ **harness**: skipped by owner

### Work plan
- ✅ **<plan_ref>**: nodes <ids> status + Log updated
- ⏸️ **plan**: none active

### Continuity
- ✅ **jump**: prompts in chat and/or `<session-cwd>/.briefs/<date>-<slug>.md`
- ⏸️ **jump**: fallback
- ✅ **desk-heartbeat**: updated

Done.
```

## When to use / not use

- **Use:** explicit close intent
- **Not:** mid-session idea → offload; mid-session continuations without closing →
  jump; harness learning mid-session → `desk-learn`; standalone handover; consolidation

## Don't

- Nag, leave PRs in draft by inertia, fold high-tier merge into blanket Y,
  reimplement capture, implement loose ideas, change related work you only read,
  force-push, or write motivational closes
- Squash, delete folders or delete local branches at close; cleanup is separate and
  proven with `git merge-base --is-ancestor <branch> origin/main`
- Move a worktree that a harness manages
- Route harness friction to wiki by default — Stage 1 harness row → `desk-learn` on Y
- Reshape `docs/plans` graphs without owner OK — status + Log only

## Optional Desk integration

When Secretary is available, reuse close_context to record progress, PRs, blockers and pending decisions with secretary status. Do not rescan: the related work sweep already ran once. Update desk-heartbeat under the instance policy after material changes. New proposals do not enable execution; autonomous preparation requires prepare-pr-v1 or specific authorization. This close works without Secretary. Brief-update publishes status; wind-down sends no mail and creates no duplicate brief.
