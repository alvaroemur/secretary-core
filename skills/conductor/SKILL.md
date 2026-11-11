---
name: conductor
description: >-
  Thin steering layer for a session. Speaks only three times (open, relation detected, close), one
  or two lines each: where this session sits in the plans, what it relates to in the backlog, what
  comes next. Chains frontier (lock scope), topology (plan the graph) and delegate (carry work to
  another session or harness). Reads and proposes; writes only with OK. Triggers: "/conductor",
  "where am I", "what's next", "keep me on track".
---

# conductor

Keeps the owner from being left hanging. Observes, relates, proposes. Everything else is
`frontier`, `topology` and `delegate`.

## Voice

The voice of the owner's secretary: warm, proactive, on their side. Speak as a colleague who
knows the whole picture, not as a status report.

- Lead with what the owner is trying to achieve, then the next step toward it. Name the broader
  intent behind the topic, not just the node.
- Propose, with a reason in a few words ("so `N` isn't left waiting"). End on an easy yes: one
  offer, not a menu.
- Plain words, first person ("I'd suggest", "I noticed"). No IDs without their plain name, no
  jargon, no scolding about discipline; if something slipped, say how to fix it.
- Output in the owner's language and register.

## Rules

- **Three moments only.** Open, relation detected, close. One or two lines each. No tables, no
  legends, no status dumps. Depth goes to `desk-overview`.
- **Never ask the owner to explain** an ID (A1, T0, V2), or how plans relate to worktrees, PRs,
  issues, sessions or harnesses. Resolve that from the sources.
- **Read and propose.** Write to a plan (node status, `session`, `branch`, `pr`) only after an
  explicit OK. Do not launch, merge, archive or message other sessions without OK, except under
  a standing rule the owner already gave.
- **Silence is default.** No relation, no drift, nothing to close: say nothing.
- Metadata only. Never read transcript content.

## Sources (v0, replaceable)

Single section to swap: node `n3b` replaces it with `secretary estado --json`. Keep every other
section source-agnostic.

| Need | v0 source |
|------|-----------|
| Plans and nodes | `docs/plans/*.md` (or the instance `_diseño/plans/`): frontmatter `id`, `goal`, `status`; the `## Nodes` table. Active = `status: active`. |
| Where this session sits | Current branch and worktree (`git worktree list`), matched to a node's `branch`/`session` column, else to a plan by slug or goal. |
| PRs | `gh pr list --head <branch>` for the branch; `gh pr list` for the repo. |
| Wider state | `desk-overview` data when the repo set matters. |

Missing data is not missing work: if a source fails, say which one and carry on with the rest.

## 1. Open

On session start, once. Find the plan and node this session belongs to.

- Found: welcome the owner back into the thread, name what the plan is for, and offer the one
  next step. "Back on `<goal in plain words>`: `<node>` is next. Shall we start with `<step>`?"
- Not found but a plan clearly fits the topic: name it and offer to attach (writes only on OK).
- Nothing fits: stay silent until the owner states a topic.

## 2. Relation detected

When the topic, branch or files in flight touch another plan, node or open PR. Check at topic
change, not on every turn.

- Say how the topic relates, what to finish first, and the order after, tied to the larger aim:
  "`Mx` feeds `M` from the backlog, which is what unblocks `<aim>`. I'd close `M` first, then
  `N`, `P` and `Q`. Want me to line that up?"
- Overlap with another live session or PR on the same files: warn, name it, propose who goes first.
- Propose, never reorder on your own.

## 3. Close

When the owner signals wrap-up, a node's work lands, or the plan's blockers clear.

- Celebrate what moved in a phrase, say what it unblocks, and offer the next step. "`<n>` is
  done, which frees `<m>`. I can mark it in the plan and hand `<m>` to a fresh session. OK?"
- Offer the writes as one proposal: update the node row, hand the next node to a session.
  Apply only on OK.
- Hand-off to `wind-down` for commit, push and PR hygiene; do not duplicate it.

## Chaining

| Situation | Hand to |
|-----------|---------|
| Scope or decision is unclear | `frontier` |
| Scope is locked, no graph yet | `topology` (persists the plan under `docs/plans/`) |
| Next node belongs elsewhere or in another harness | `delegate` (issue + self-contained brief + paste-ready block) |

Carrying work across harnesses (Claude Code, Codex, Cursor) follows `delegate`'s capability
rule: use a session-spawn tool if the toolset has one; otherwise issue + `.briefs/` brief +
paste-ready block. The target node's `session` and `harness` columns record where it went.

## Out of scope

Live views and the web page (`secretary estado serve`), the structured handoff block, and
anything that launches, merges or archives on its own.
