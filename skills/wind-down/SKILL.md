---
name: wind-down
metadata:
  close-contract: "4"
description: >-
  End-of-session ritual. Does the safe steps first (commit, push, PR ready,
  rescue uncommitted outputs, remove integrated worktrees), then shows one
  proposal that recommends merging by default, and closes with a confirmation
  that says what was done, what is still running with its brief, and whether
  the session can be archived. Continuity always goes through jump and always
  ends in a paste-ready block. Marks briefs done or superseded. Triggers:
  "/wind-down", "let's wrap up", "close this". NOT for mid-session ideas,
  mid-session continuations without closing, standalone handover, or memory
  consolidation.
user-invocable: true
---

# wind-down — end-of-session ritual

Orchestrator. Detects the open loops of this session, does what is safe without
asking, routes the rest to the skill that resolves it, and asks once.

Doctrine: `rules/skills-contract.md` · related issues doctrine · GitHub signatures ·
instance git policy `canon/rules/git/` (`integracion.md`: worktrees, ready to integrate, merge)

## Shared close context

Collect session state once. Identify the repos and files touched by this session; do not infer them from the last commit. State uncertainty rather than attributing another session's edits to this one. Act only on this session's work; other work is read, never changed (see **Related work sweep**), except the cleanup of integrated worktrees under **Safe steps**.

Build one `close_context`: session id, actual checkout, main checkout (`git rev-parse --path-format=absolute --git-common-dir` → its parent), whether the checkout is a harness worktree, branch, commit, touched files and their status, decisions and reasons, result, blockers, next action, PR, references, the brief this session resumed from (if any) and one brief path. Query the branch PR and unpublished commits once. No auxiliary session or reflection agent is needed.

Pass this object to project sync, handover and jump. They reuse it instead of repeating git or conversation collection. Handover is the only brief writer; jump uses that brief.

### Outputs for another session (survive the archive)

Every output another session or harness must read (briefs, analysis reports, prompts) must survive the archive: archiving a harness session discards the uncommitted files of its worktree. Never use scratchpad or `/tmp` for them.

- Briefs: `.briefs/`. Analysis: `.analysis/<topic>/`. Both are versioned (BRF-6), except in public repos: there they stay local and ignored (`.gitignore`), and a session in a harness worktree hands them over with the paste-ready block.
- The paste-ready prompt carries the essentials itself; it cites the file by absolute path and, when it lives on a topic branch, as `<branch>:<path>` (readable with `git show origin/<branch>:<path>` before the merge).
- **Harness guard (XCK-4).** Some harnesses block file tools from a harness worktree to the main checkout (Claude Code: "This session is running in an isolated git worktree…"). Never work around it with the shell.
  - Read-only sessions (evaluators, reviews) run without a worktree and write straight to the main checkout.
  - A session in a harness worktree writes the output inside its worktree and puts, in the paste-ready block, the absolute path **and the full content**.
  - With a topic branch, the session commits its output in `.briefs/` or `.analysis/` on that branch and pushes it. That is the rescue.
  - Without a topic branch, the rescue is done by a session that runs in the main checkout: the original session when it ingests the block, or wind-down run from there. It copies the content to `<main-checkout>/.briefs/` or `.analysis/`, routes the commit, and says the other session can be archived.

### Related work sweep (read-only)

For each repo touched, read once and **report, never act**:

```bash
git -C <repo> worktree list --porcelain
gh pr list --repo <owner/repo> --state open --json number,title,headRefName,files
gh issue list --repo <owner/repo> --state open --json number,title,labels
```

Relate an item when it touches the same files or the same scope (`<type>(<scope>)`, `hilo:` label). List it as **close before** (it blocks or conflicts with this change: same files, a dependency PR) or **related** (same topic, no conflict). Related PRs that are ready get their own merge recommendation in the proposal.

### Co-changes (what this change drags along)

1. **References:** search the touched file names, skill names and changed identifiers in `AGENTS.md`, `CLAUDE.md`, `README*`, `docs/`, `tests/`, rules and the instance policy (`rg -l '<name>'`). Any hit not updated in this session is a co-change candidate.
2. **Installed copies:** when skills or playbooks changed, compare the hash of each installed copy with the versioned source (`shasum`). A mismatch means a redeploy is pending.

Report co-changes as items; do not edit outside this session's topic without the owner's OK.

An optional `secretary efficiency close-snapshot` can supply mechanical git state when available. It is not required.

## Instance setup

```bash
CFG=$(secretary config show)
export SECRETARY_INSTANCE="${SECRETARY_INSTANCE:-$(echo "$CFG" | jq -r .instance)}"
```

Workspace/repo routing for handover destinations and offload context: **instance
`AGENTS.md`** (Cowork/Dev layout, client map). Do not embed absolute cwd tables.

## Principles

- **Safe first, then ask once.** Everything in **Safe steps** runs before the proposal and shows up as ✓ inside the item it belongs to. The proposal asks only what needs the owner.
- **Merge by default.** A ready PR from this session is recommended for merge unless its work is still in progress. Say why when the recommendation is not merge.
- **Integrated means removed.** Once a branch is in `origin/main`, its worktree, local branch and remote branch go away (see **Cleanup rule**). No separate cleanup section: cleanup is a ✓ in the item.
- **One topic, one worktree, one PR.** Each topic lives in `<repo>/.wt/<branch with "/" → "-">`, on a branch cut from `origin/main`, with one PR. The main checkout stays on a clean `main`. The instance repo keeps direct commits to `main`, but must end clean and pushed.
- **Ready to integrate is the close target.** A topic is **ready** when the PR is open and not draft, `mergeable` is clean, CI is green (or the repo has no required checks) and human review comments are resolved. Anything missing becomes a named blocker.
- **Plain words.** Name things by what they are (branch, PR, brief, prompt). No internal jargon, no coaching, no condescending lead-ins, no reproach.
- **Capture, don't execute.** Loose ideas → offload, not implementation now.
- **"I don't know" parks.** Log open questions and continue.

## Cleanup rule (CLN-2)

Remove a worktree and its branches without asking only when **all four** hold:

1. Integrated: `git merge-base --is-ancestor <branch> origin/main` (after `git fetch origin`).
2. Clean: `git -C <wt> status --porcelain` is empty (no changes, no untracked files).
3. Unused: no process has its cwd there (`lsof -a -d cwd -Fn 2>/dev/null | grep -F "<wt>"` is empty).
4. Not the folder this session runs in.

Then:

```bash
git -C <repo> worktree remove <wt>
git -C <repo> branch -d <branch>
git -C <repo> ls-remote --exit-code --heads origin <branch> >/dev/null && git -C <repo> push origin --delete <branch>
```

If a condition fails, keep everything and name the failing condition in the item. Harness-managed worktrees (`.claude/worktrees`, `~/.codex/worktrees`, `~/.cursor/worktrees`) are never removed here; the harness archives them. Applies to this session's branches and to any other integrated worktree found by the sweep in the touched repos.

## Brief lifecycle (BRF-1)

Briefs live in `<main-checkout>/.briefs/` with frontmatter `status`:

| status | Meaning | Where |
|---|---|---|
| `pending` | Written by handover; nobody resumed it yet, or the work it hands over is not finished | `.briefs/` |
| `done` | The work it handed over is finished | `.briefs/_archivo/` |
| `superseded` | A newer brief replaces it, or it went stale (>30 days without use) | `.briefs/_archivo/` |

At close:

- The brief this session resumed from → `done` when its work is finished here; keep `pending` and point to the new brief otherwise (the new one supersedes it: set the old one `superseded` with `superseded_by: <new path>`).
- A new brief for a thread that already had a `pending` brief supersedes it the same way.
- Moving to `_archivo/` adds `closed: <YYYY-MM-DD>`. Move, never delete: `git mv` when tracked, and commit the move with the session's work.

## Skill chain

| Loop | Routes to |
|------|-----------|
| Loose idea | offload (blob or with-context) |
| Thread continues elsewhere | handover (one brief) + jump (paste-ready block) |
| Durable knowledge | offload (wiki vs issue triage); do not write wiki directly |
| Project milestone / deliverable | `desk-write` (wiki theme) |
| Harness / system friction | `desk-learn` → offload (default ISSUE) |
| Branch / PR from session | safe steps → merge recommendation → `desk-merge` |
| Related open work / co-changes | report; ready related PRs get a merge recommendation |
| Chat-reported progress not persisted | `secretary status` |
| Project hygiene | `desk-project-sync` |
| Active work plan | `docs/plans/<slug>.md` or `_diseño/plans/<slug>.md`: node status + Log for nodes touched |
| Open PR with unread comments | mention `pr-sync` for the next session |

## Procedure — three stages

### Stage 0 — Safe steps (no question)

Scan repos touched, then do, in order, and record each result as a ✓ (or ⚠️ with the reason) for its item:

1. **Worktree check.** Expected: folder `<repo>/.wt/<branch-slug>`, branch `<scope>/<desc>`, main checkout on a clean `main`. Correct mechanically:
   - Folder name ≠ branch, created by hand → `git worktree move <old> <repo>/.wt/<branch-slug>`.
   - Branch `claude/*`, `codex/*` or another harness prefix → `git branch -m <scope>/<desc>` before the PR.
   - Topic work on the main checkout → commit on a topic branch, `git switch main` in the main checkout, `git worktree add <repo>/.wt/<branch-slug> <branch>`.
   - Harness-managed worktree → do not move it: commit + push, `git switch --detach` there, then `git worktree add <repo>/.wt/<branch-slug> <branch>`.
   Stop on that topic only (report, propose the command) when another live session uses the folder, there are uncommitted changes not from this session, or the destination exists.
2. **Rescue uncommitted files (XCK-3, XCK-4).** In the session's checkout, `git status --porcelain --ignored` and classify each file:
   - Part of the topic → commit on the topic branch.
   - Output for another session (`.briefs/`, `.analysis/`, reports, prompts) → commit on the topic branch when there is one. Without a topic branch: in the main checkout it is already in place (route its commit with the rest); in a harness worktree it cannot cross the guard, so list each file with its absolute source path and target `<main-checkout>/<same relative path>`, and put its full content in the paste-ready block.
   - Neither (build cache, scratch) → leave it, list nothing.
   When wind-down runs **from the main checkout**, it also rescues the outputs of harness worktrees in the touched repos (pasted blocks it received, or files under `<repo>/.claude/worktrees/*/.briefs|.analysis`): copy to the main checkout, report source → destination, and say which session can now be archived.
   Any output left unrescued blocks archiving (Stage 2: "can you archive?" = no, with the list of what to copy and where).
3. **Commit, push, PR.** Commit per topic (Conventional Commits per instance `AGENTS.md`), push, open the PR not draft, update the body if it drifted. Sign per **GitHub signature**.
4. **Cleanup.** Apply the **Cleanup rule** to every integrated worktree in the touched repos.
5. **Briefs.** Apply the **Brief lifecycle** to briefs this session resumed or wrote.
6. **Status sweep.** Persist chat-reported progress not yet recorded (`secretary status`).

Never force-push. Never push code to `main` without a branch. On failure, record ⚠️ and continue.

### Stage 1 — Proposal

Then gather what needs the owner:

- **Merge.** For each ready PR of this session (and ready related PRs): recommend merge unless the work is still in progress. Give a check under 2 minutes: command + expected result, or what to look at in the diff. Tier still applies: **low tier** (`*.md`, `*/memory/`, `wiki/`, notes) folds into the single answer; **high tier** (code, `.github/`, `package.json`, instance YAML, build scripts; mixed or unclear → high) shows a diff summary in its item. Check `gh api repos/<owner/repo> -q .allow_merge_commit` first.
- **Not ready.** Name the missing piece (CI, review, conflicts) and the next step.
- **Issues touched.** If the session closed, commented substantially on, or merged a PR resolving an issue, run the bidirectional related-issues check.
- **Project sync (Cowork/Dev).** AGENTS.md, scratch purge, layout, entity-contract / EDT drift.
- **Work plan.** For an `active` plan (or `plan_ref` in session): node status changes + Log rows for nodes touched. Do not reshape the graph without owner OK.
- **Memory.** Milestones (`desk-write`), harness friction (`desk-learn`), durable knowledge (offload).
- **Continuity (default when work is still in progress).** handover writes or updates the brief; jump builds the restart prompt from `close_context` without a second round of questions (one prompt per open thread, best-fit proposal, no tier choice). The prompt is for another harness: it starts by checking whether the work was already done elsewhere and only references paths another agent can read.

#### Stage 1 template

Render only sections with items. Each item carries its ✓ from Stage 0. Numbered items are the ones that need an answer.

````markdown
## Close — <session topic in a few words>

### What this session did
- <one line per result, anchored in what happened in the chat>

### Code and PRs
- **<repo>** `<branch>` — ✓ committed · ✓ pushed · ✓ PR #<N> ready
  1. 🔀 Merge PR #<N>? Recommended: yes. Check: `<command>` → `<expected>`
- **<repo>** `<branch>` — ✓ PR #<N> · ⏳ missing <CI | review | conflicts> → <next step>
- **<repo>** `.wt/<old-branch-slug>` — ✓ integrated · ✓ worktree, local and remote branch removed
- **<repo>** `.wt/<branch-slug>` — ⚠️ integrated, kept: <failing condition>

### Issues and project
- ✓ issues checked both ways: #<N> <comment posted | already consistent>
  <n>. 🔗 Update issue #<N> (`## Relacionado`)? Recommended: yes
- ✓ project sync: <AGENTS.md | scratch purge | layout | EDT drift> — <result>

### Related work
- 🟠 close before: PR #<N> (`<branch>`) — touches `<files>`
  2. 🔀 Merge PR #<N> too? Recommended: yes. Check: `<check>`
- ⚪ related: issue #<N> — same scope `<scope>`
- 🧩 co-change: `<file>` mentions `<identifier>`
  3. Update it in this PR? Recommended: yes

### Memory and plan
  4. 📝 Note `<milestone>` in the `<topic>` wiki theme? Recommended: yes
  5. 🧠 Log harness friction `<what>` as an issue (`desk-learn`)? Recommended: yes
- ✓ plan `<plan_ref>` node <id>: <old> → <new>, Log row added

### Continuity
- ✓ brief `<abs path>` (pending) · ✓ previous brief `<abs path>` → superseded
- ✓ rescued `<file>` → `<abs path in main checkout>` (or ⚠️ to copy: `<abs source>` → `<abs target>`, content in the block below)
- Restart prompt in the last block; the harness card is offered after the close

Reply with numbers (`1 3`), `all`, or `none`, or edit the block:

```text
<n> <kind> <ref>: yes
```

Paste this in a new session (any harness) to continue:

```text
<restart prompt from jump>
```
````

The reply block has exactly one line per numbered item, in the same order and numbering (`<n> merge PR #<N>: yes`, `<n> co-change: yes`, `<n> wiki: yes`, …); the line above is the shape, not a list to copy. It is one fenced `text` block, no fence inside it, no rendered markdown inside it. When something continues, the restart prompt block follows it and is the last element of the answer; with nothing continuing, the reply block is the last. Emojis mark the kind of item: 🔀 merge, 🔗 issue, 🧩 co-change, 📝 memory, 🧠 friction, 🟠 blocks, ⚪ related, ⏳ waiting, ⚠️ kept or failed.

### Stage 2 — Execute and confirm

Run what the owner accepted: merges through `desk-merge` (merge commit, then cleanup), memory routes, plan updates. Then decide whether the session can be archived:

- **yes** — nothing in progress, everything committed or rescued, no merge pending on this session.
- **yes, with conditions** — archivable once the owner does something outside the session (merge a PR, read the brief, check a related session). Name each condition.
- **no** — an output is still only in a harness worktree, work is mid-edit, or a running process depends on this folder. Say why and list what to copy and where.

**GitHub signature (mandatory)** before any `gh pr create`, `gh issue create`, or
`gh issue comment` this skill emits — prefer `secretary signature wind-down
--runtime <actual-runtime>` (or its `--mark` / `--footer` outputs). Do not claim
another harness as the author.

**Main checkout gate** before declaring close, when instance policy requires the
secretary checkout on `main` clean except untracked.

If the close changed material state, the next heartbeat routine run picks it up
(`playbooks/sec-heartbeat/procedure.md`); do not run it by hand.

#### Stage 2 template (confirmation)

````markdown
## Session closed

### Done
- ✓ <result> — PR #<N> merged (merge commit) · worktree and branches removed
- ✓ <result>

### Still in progress
- ⏳ <thread> — brief `<abs path>`

### Can you archive this session?
**<yes | yes, with conditions | no>** — <why>
- <condition or check before archiving: e.g. confirm the other session on `<branch>` did not continue this>

### Check before archiving
- <what to look at, under 2 minutes>

### Resume
Paste this in a new session (any harness). I can also create a harness session card for it: reply `card`.

```text
<restart prompt from jump: starts by checking whether the work is already done, then objective, first file to read with absolute path, completion criterion>
```
````

Omit "Still in progress" and "Resume" when nothing continues. When something continues, the restart block is the default and the last element of the answer; the harness card is only an option offered after it, never created on its own.

## When to use / not use

- **Use:** explicit close intent
- **Not:** mid-session idea → offload; mid-session continuations without closing →
  jump; harness learning mid-session → `desk-learn`; standalone handover; consolidation

## Don't

- Ask about something Stage 0 can do safely
- Leave PRs in draft by inertia, fold a high-tier merge into a blanket answer without its diff summary, squash, or force-push
- Remove a worktree or branch that fails one of the four cleanup conditions, or a harness-managed worktree
- Delete a brief (move it to `_archivo/`)
- Reference scratchpad, `/tmp` or harness-worktree paths in anything another session reads
- Work around a harness guard with shell redirection
- Change related work you only read (beyond the cleanup rule), implement loose ideas, or reshape `docs/plans` graphs
- Write motivational or condescending lines

## Optional Desk integration

When Secretary is available, reuse close_context to record progress, PRs, blockers and pending decisions with secretary status. Do not rescan: the related work sweep already ran once. New proposals do not enable execution; autonomous preparation requires prepare-pr-v1 or specific authorization. This close works without Secretary. wind-down sends no mail and creates no duplicate brief.
