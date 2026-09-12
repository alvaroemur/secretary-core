---
name: frontier
description: >-
  Interrogate the owner on every material aspect of a plan, decision, or idea until
  shared understanding is locked. Uses a decision tree with frontier logic: ask only
  what already has prerequisites resolved, in batched rounds with a recommended
  answer each; investigate code/environment instead of asking verifiable facts.
  Always visualize the decision tree. After explicit confirmation, hand off to
  execution design (work graph). Triggers: "/frontier", "grill this", "stress-test
  this idea". NOT for writing a paste-ready meta-prompt for another session alone.
user-invocable: true
---

# frontier

Build **shared understanding** of a plan, decision, or idea in this session via
structured interrogation. Does not execute during grilling.

Doctrine: `rules/skills-contract.md`

## Decision tree

Decompose the idea into a decision tree. Dependent decisions stay blocked until
parents resolve. Keep the tree as the source of truth for what to ask next.

**Always materialize the tree** at the end of each round and again at the confirmation
gate:

- **Mermaid** flowchart by default
- **Text** `A -> B -> C` when the tree is trivial (< 4 nodes) or the owner asks for text

Showing the tree is not optional. Persisting it as a separate artifact is optional
unless the owner asks.

## Frontier logic

Each round, ask only questions whose prerequisites are already resolved (the
**frontier**). Do not speculate on branches whose parents are still open.

## Autonomous factual research

Before asking anything verifiable in code or the environment, investigate it.
Use non-blocking explore subagents when useful; keep asking other frontier
questions that do not depend on that result.

## Round structure

Present **all** current frontier questions at once, numbered, each with its own
recommended answer. Prefer discrete option UIs when the harness provides them;
otherwise numbered text. Wait for the owner's answers before the next round.

Do not ask one-by-one when several questions are already on the frontier.

## Session card

At start (and refresh when goal/scope shifts), emit:

```markdown
## frontier

**goal:** <one line>
**in_scope:** <bullets or short clause>
**out_of_scope:** <bullets or short clause>
**cwd:** <repo or path>
**constraints:** <or none>
**open_questions:** <count or list>
**plan_ref:** <path | null>
**decision_tree:** <mermaid block or A -> B text>
```

Use these field names. `plan_ref` stays null until a durable plan exists.

## Evolution

Each owner answer closes one or more decisions and expands the frontier. Repeat
until the frontier is empty: every branch explored, nothing tacitly assumed.

## Confirmation gate

Before acting (code, formal plan, execution), the owner must **explicitly** confirm
the shared understanding. Mid-grill "ok" / "dale" does not count — only approval of
the final summary.

After that yes: **stop grilling**. Hand off to work-graph execution design (same
field names as that skill's header: goal, cwd, plan_ref, …). If that design step
is unavailable, fallback binary only:

1. Direct in session (`in_session`)
2. Autonomous agent

Do not start agents until the owner picks an execution graph (or the fallback).

## Don't

- Change code during grilling
- Collapse all questions into one round ignoring frontier logic
- Keep grilling after the confirmation gate
- Name platform-specific callers or hardcode instance paths / emails / repos
