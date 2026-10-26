---
name: frontier
description: >-
  Interrogate the owner on every material aspect of a plan, decision, or idea until
  shared understanding is locked. Uses a decision tree with frontier logic: ask only
  what already has prerequisites resolved, in batched rounds with a recommended
  answer each; investigate code/environment instead of asking verifiable facts.
  Always show the decision tree as a text tree. After explicit confirmation, hand off to
  execution design (work graph). Triggers: "/frontier", "grill this", "stress-test
  this idea". NOT for writing a paste-ready meta-prompt for another session alone.
user-invocable: true
---

# frontier

Build **shared understanding** of a plan, decision, or idea in this session via
structured interrogation. Does not execute during grilling.

Doctrine: `canon/rules/skills/skills-contract.md` (resolve from the active instance).

## Decision tree

Decompose the idea into a decision tree. Dependent decisions stay blocked until
parents resolve. Keep the tree as the source of truth for what to ask next.

**Always materialize the tree** at the end of each round and again at the confirmation
gate:

- **In chat:** an indented text tree with state marks (✅ resolved · ❓ on the frontier ·
  ⏳ blocked by a parent · ✖️ discarded or superseded). Never Mermaid in chat: some
  harnesses do not render it.
- **In the scope record:** Mermaid is allowed (and the text tree is fine too).

```text
CMP-1 ✅ name: "compromisos"
├─ CMP-2 ✅ one-off cleanup
└─ CMP-3 ❓ auto-expiry exception
   └─ CMP-4 ⏳ weekly summary format
```

## Frontier logic

Each round, ask only questions whose prerequisites are already resolved (the
**frontier**). Do not speculate on branches whose parents are still open.

## Autonomous factual research

Before asking anything verifiable in code or the environment, investigate it.
Use non-blocking explore subagents when useful; keep asking other frontier
questions that do not depend on that result.

## Question IDs

Each question gets a short ID: a 3-letter prefix for the front it belongs to plus a number
(`CMP-2`, `PLT-5`). Pick prefixes the owner can read without a key (`CMP` commitments,
`PLT` templates), keep them stable across rounds, and never reuse a closed ID for a new
question; a variant takes a suffix (`PLT-5b`).

## Round structure

Present **all** current frontier questions at once. Each round, in this order:

1. **First line:** `plan_ref` as a link to the scope record (the owner should not have to
   search for it). If the record is blocked, say so on this line.
2. **Legend:** one line with the prefixes used in this round and their meaning.
3. **Questions:** each with `ID — title`, context in a few lines, options when discrete,
   and the recommended answer with its reason.
4. **Tree:** the updated text tree.
5. **Reply block:** last element, one fenced ```text block with every ID prefilled with
   the recommendation, ready to copy and edit. No nested fences.

```text
CMP-3: sí
PLT-5: opción 2
PLT-7: <recomendación>
```

The owner may answer by ID with numbers or keywords (`CMP-3 sí`, `PLT-5: 2`) or by
editing the block. Prefer discrete option UIs when the harness provides them; still emit
the reply block.

If the complete round exceeds the UI limits, present the entire round as text. Do not
truncate or split the frontier to fit a form. Follow the active harness rules for pending
questions and waiting.

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
**decision_tree:** <text tree>
```

Use these field names. `plan_ref` points to the actual scope record, even while it
is a draft. Use null only until the file exists; never substitute a vague status
for its path or claim an unsuccessful write was persisted.

## Evolution

After each owner answer, close resolved decisions, update the tree, and perform
newly unblocked factual research in the same turn. Present all newly available
frontier questions with recommendations and the updated tree before ending the
turn. Do not end with a promise to perform an available read later.

An empty frontier is not sufficient for completion: all material decisions must
be resolved or explicitly discarded, with no unresolved dependencies. If external
evidence is unavailable, record what is missing, what was tried, and how to unblock
it. Do not treat blocked decisions as resolved or ask the owner facts that can
still be investigated.

## Durable scope record

At the start, reuse the relevant existing document or create a draft scope record
in the active project's permitted planning location. Set `plan_ref` to that file.
Recording the discussion is part of grilling; it does not approve implementation
or constitute a formal execution plan. Respect local write permissions. If writing
is blocked, say so, provide the pending record in chat, and keep persistence marked
as blocked rather than claiming the checkpoint exists.

Before ending each round, and after every material scope change or research
finding that changes a decision, update the record with:

- Current goal, scope, constraints, and exact wording where it affects acceptance.
- Accepted decisions and their relevant reasons, distinguished from recommendations
  awaiting an answer and assumptions awaiting verification.
- Verifiable findings with source references and material uncertainties.
- Current decision tree, unresolved questions, dependencies, and next frontier.
- Confirmation status and the scope to which any approval applies.

Keep a concise chronological change log identifying each round or source message.
When a decision changes, mark the earlier decision as superseded and retain why;
the current scope must remain unambiguous. Preserve decision-relevant detail, not
a transcript of every tool call. Check that the written record reflects the round
before presenting the next round or final confirmation summary.

If the document already contains an approved execution graph, keep scope notes
and the change log separate from it. Recording new scope does not authorize
reshaping that graph or extending an earlier execution approval.

After compaction, re-entry, or handoff, read `plan_ref` before continuing. Reconcile
it with available newer messages; recover omitted decisions from accessible history
instead of asking them again. Flag any unresolved gap. Carry the actual path into
the final handoff so execution design can consume the agreed scope.

## Final summary

When the frontier is empty, present the final summary grouped by front. Each point cites
the source IDs (`CMP-2, CMP-3`) so the owner can return to that round and adjust. Open
with `plan_ref` as a link, as in every round, and close with a ```text reply block
(`confirmo` or the IDs to reopen).

## Confirmation gate

Before designing execution or acting (code, formal execution plan, execution),
the owner must **explicitly** confirm the shared understanding. Mid-grill "ok" /
"dale" does not count — only approval of the final summary.

After that yes: **stop grilling**. Hand off to work-graph execution design (same
field names as that skill's header: goal, cwd, plan_ref, …). If that design step
is unavailable, route each front with the common reply format
`<ID>: aquí | sesión | agente | dream` (this session · new parallel session · subagent ·
dream queue), prefilled in a ```text block.

Do not start agents until the owner picks an execution graph (or the fallback).

## Don't

- Change code during grilling
- Collapse all questions into one round ignoring frontier logic
- Keep grilling after the confirmation gate
- Name platform-specific callers or hardcode instance paths / emails / repos
