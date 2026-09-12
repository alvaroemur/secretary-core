---
name: jump
description: >-
  From any in-progress session, propose continuation archetypes (replay, QA, next
  plan/EDT step, lateral fork) and emit paste-ready prompts at three context tiers
  (surgical, operational, autonomous). Owner picks which prompts to generate. May
  hand a prompt to offload/restart elsewhere. Triggers: "/jump", "where next",
  "continuation prompts". NOT for session hygiene, scope grilling, or work-graph
  design.
user-invocable: true
---

# jump — continuation prompts from live session state

Generate **where next** options and prompts. Does not close the session, push, or merge.

Doctrine: `rules/skills-contract.md`

## When to use / not use

- **Use:** mid-session continuations; owner wants replay/QA/next-step prompts;
  end-of-session continuity when there was material work.
- **Not:** git/PR hygiene; designing a work graph; locking scope; parking a single
  already-named idea verbatim (use offload/restart for that).

## Scan (read, don't ask)

```bash
git status -sb
git diff --stat
git branch --show-current
```

Also read, when present:

- Active conversation artifacts
- `docs/plans/*.md` with `status: active` (prefer the one cited as `plan_ref`)
- cwd `contract.yaml` if `kind: entity` (EDT activities — read-only)
- `.cursor/tasks/` briefs in the repo

From an active plan: list nodes with `status` in `pending` | `blocked` | `running`.
Prefer continuations anchored to those node ids.

## Archetypes

Propose only archetypes that fit. Omit empty ones.

| Id | Name | When |
|----|------|------|
| replay | Replay / transfer | Methodology just used; another dataset, client, or subject exists |
| qa | Deep review / QA | Artifacts were produced; worth audit, tests, or consistency pass |
| next | Next plan / EDT step | Active plan has a ready node, or entity contract has next pending activity |
| fork | Lateral fork | Adjacent idea that should not derail this thread |

Each row: one-line intent + suggested default tier. When anchoring to a plan node,
cite `node:<id>` in the intent line.

## Context tiers

Owner picks **per archetype** (not one global tier).

| Tier | Contents |
|------|----------|
| **Surgical** | 1–2 lines. Verb + target. Assumes the next agent reads the repo. |
| **Operational** | Plan node id and/or EDT id, input paths, expected deliverable. No full contract dump. |
| **Autonomous** | Self-contained: goal, plan_ref excerpt or contract excerpt, acceptance, no-goals, constraints. Fit for a clean session or offload. |

## Loop

1. Scan. Build the archetype table with a recommended tier each.
2. Ask which rows to emit, and which tier per row (defaults in the table).
3. Write only the chosen prompts — paste-ready, no narration inside them.
4. Offer handoff per prompt:
   - **Stay** — leave in chat (and optionally `.cursor/tasks/YYYYMMDD-<slug>.md`).
   - **Offload** — pass the prompt to the harness offload/restart playbook (issue +
     clean-context brief). Jump does not spawn sessions itself.

## Prompt shapes

**Surgical**

```
<imperative one-liner>. Repo is already the cwd.
```

**Operational**

```
Do <action> for plan node <id> (mode <mode>) — <title>.
Inputs: <paths>.
Output: <deliverable path or artifact>.
Do not reshape docs/plans graph or mutate contract.yaml without owner OK.
```

**Autonomous** — prose block, no headings inside, ~120–200 words. Include: destination
cwd or repo, plan_ref and/or EDT id, acceptance, explicit no-goals, "do not mutate
contract.yaml; append plan Log only".

## Continuity fallback (callers)

If jump is unavailable or the session had no material work, callers must not block
close. Two lines max:

```
Continuity: local handover in .cursor/tasks/ <or> none.
Open issues: <list or none>.
```

## Don't

- Close the session, push, or merge
- Invent EDT activities or plan nodes
- Mutate `contract.yaml` or reshape a plan graph
- Emit all three tiers for every archetype unless asked
- Offload without owner pick
