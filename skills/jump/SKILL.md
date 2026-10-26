---
name: jump
metadata:
  close-contract: "3"
description: >-
  From any in-progress session, propose continuations that fit the context (new
  inputs, revisit assumptions, QA with another model or harness, related
  commitments, the next plan step, a lateral fork…) and emit each as a
  paste-ready block that starts by checking whether the work is already done.
  Can queue a step for dream. The harness session card is an option after the
  block, never a replacement. Triggers: "/jump", "where next", "continuation
  prompts". NOT for session hygiene, scope grilling, or work-graph design.
user-invocable: true
---

# jump — continuation prompts from live session state

Proposes **where next** and writes the prompts. Does not close the session, push, or merge.

Doctrine: `rules/skills-contract.md`

## Integration with wind-down

When given `close_context`, reuse its state, decisions, active plan and brief. Do not repeat git scans, read other worktrees or create another brief. Do not open a second round of questions: emit one prompt per open thread with the best-fit continuation, and list other proposals as one line each that the owner can ask for. This rule overrides the **Loop** below.

## When to use / not use

- **Use:** mid-session continuations; end-of-session continuity (via wind-down).
- **Not:** git/PR hygiene; designing a work graph; locking scope; parking a single
  already-named idea verbatim (use offload for that).

## Scan (read, don't ask)

```bash
git status -sb
git diff --stat
git branch --show-current
```

Also read, when present:

- Active conversation artifacts and what the owner said they still doubt or want
- `docs/plans/*.md` or `_diseño/plans/*.md` with `status: active` (prefer `plan_ref`); nodes `pending` | `blocked` | `running`
- cwd `contract.yaml` if `kind: entity` (EDT activities — read-only)
- `<main-checkout>/.briefs/*.md` with `status: pending`
- Open commitments of the owner linked to this topic (`secretary acc`, when available)
- Open PRs and issues on the same scope

## Proposals (no fixed menu)

Build proposals from what the scan found, not from a closed list. Kinds that often fit, as examples:

- **New inputs** — a source that arrived or changed since the work was done (meeting, mail, data cut).
- **Revisit assumptions** — a decision taken under doubt that a fresh session should test.
- **QA with another model or harness** — the work is done; a blind second pass catches what this session cannot (`cross-check` when it needs a panel).
- **Related commitment** — an open commitment of the owner that this work unblocks or advances.
- **Next plan / EDT step** — a ready node (`node:<id>`) or the next pending activity.
- **Replay** — the method just used applies to another dataset, client or subject.
- **Lateral fork** — an adjacent idea that should not derail this thread.

Each proposal: one line with intent, why now (the evidence), and where it runs (`here | session | agent | dream`). Omit kinds with no evidence. Rank by usefulness to the owner, not by kind.

## Queue for dream (JMP-4)

When a proposal can run without the owner (clear inputs, verifiable output, no decision pending), offer `dream` as its destination: open an issue with the `dispatch:execute` label in the destination repo (it must be in `dispatch.executor.repos`), with the prompt as body; or, for work without a repo, append it under `## Pendientes` in `$SECRETARY_INSTANCE/subsystem/dream/queue.md`. Ask before either: both are writes outside the session. Dream evaluates it with its own filters; queuing does not guarantee a PR.

## Prompt rules

Every prompt, whatever its size:

1. **Starts by checking whether the work is already done** elsewhere: merged PRs, other branches or worktrees, newer briefs, the file it would produce. If done, the agent reports where and stops.
2. Names the destination repo or folder as an absolute path, the objective, the first file to read and an observable completion criterion.
3. Carries the essentials itself; does not depend on chat history or a harness-specific tool.
4. References only paths another agent can read: the main checkout (`.briefs/`, `.analysis/`, repo files), Drive URLs. Never scratchpad, `/tmp` or a harness worktree.
5. Cites the brief (absolute path) when there is one, and says to mark it `done` (move to `.briefs/_archivo/`, add `closed:`) when the work it hands over is finished.
6. States no-goals: do not reshape `docs/plans` graphs or mutate `contract.yaml` without owner OK.

Size follows need: a one-line instruction when the next agent only has to read the repo; a 120–200 word self-contained prose block when it starts cold.

## Output

- Each prompt goes in **one fenced `text` block**, with no fence and no rendered markdown inside. When there is one prompt, its block is the **last element** of the answer.
- Several prompts: one block each, each preceded by a one-line label; the last block ends the answer.
- After the block(s), never before and never instead: offer the harness session card as an option (`reply "card" to start it as a session here`). Create it only on that reply.

Prompt shape (prose, no headings inside):

```text
Before starting, check whether this is already done: <where to look: PRs, branches, newer briefs, the output file>. If it is, report where and stop.
Repo: <absolute path>. Objective: <one sentence>. Read first: <absolute path of brief or file>.
<Inputs and context the next agent needs, in prose.>
Done when: <observable criterion>. Then mark the brief done (move it to .briefs/_archivo/ with closed: <date>).
Do not <no-goals>.
```

## Loop (standalone)

1. Scan. Build the proposal list (one line each, recommended first).
2. Ask which to emit, by number or keyword, with a reply block as the last element.
3. Emit the chosen prompts per **Output**. Offer the card after them.

## Don't

- Close the session, push, or merge
- Invent EDT activities or plan nodes
- Mutate `contract.yaml` or reshape a plan graph
- Ask the owner to pick a context tier or archetype
- Create a harness session card without the owner asking for it
- Emit a prompt that skips the "already done?" check
