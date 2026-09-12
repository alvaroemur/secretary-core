---
name: topology
description: >-
  Design a multi-agent work graph for scoped work: nodes in three modes (in_session,
  autonomous, parallel_hitl), joins as edges, optional named subgraph patterns
  (gauntlet, bake_off, fan_out). Persists a durable plan under docs/plans/ that
  sessions update together. Triggers: "/topology", "how should we run this",
  "work graph", "multi-agent layout". NOT for locking scope or writing continuation
  prompts alone.
user-invocable: true
---

# topology — work-graph execution design

Design **how** scoped work runs across agents and sessions. Output is a **work graph**
plus an optional durable plan file — not a single global strategy menu.

Doctrine: `rules/skills-contract.md`

## When to use / not use

- **Use:** owner asks how to split or stage work; after scope is locked; mid-session
  redesign of execution.
- **Not:** locking requirements; parking a one-line idea; end-of-session hygiene;
  writing continuation prompts as the primary job.

## Header (always — solo or after scope lock)

Emit this block before the graph:

```markdown
## topology

**goal:** <one line>
**cwd:** <repo or path>
**plan_ref:** <docs/plans/<slug>.md | none>
**node_counts:** in_session N · autonomous N · parallel_hitl N
**ready_to_run:** <node ids with deps met> | none
```

Same field names everywhere. Do not invent synonyms.

## Node modes (exactly three)

| Mode | Meaning |
|------|---------|
| `in_session` | This session; owner in the loop |
| `autonomous` | Agent runs without owner in the loop (subagent / background) |
| `parallel_hitl` | Another live session **with the owner**; main session later consumes the result |

**Joins are edges**, not nodes. Label them (`consume`, `blocks`, `merge`). A node may
run only when inbound join conditions are met.

Do not add modes such as `join` or `async_dispatch`. Overnight / issue runs are composed
with these three modes + edges + the named patterns only (`gauntlet` / `bake_off` / `fan_out`).

## Named subgraph patterns

Expand patterns into nodes + edges. They are not modes.

| Pattern | Expands to |
|---------|------------|
| `gauntlet` | Builder (`autonomous` or `in_session`) ↔ critic loop until a named fetchable bar wins |
| `bake_off` | 2–3 parallel `autonomous` nodes, optionally in separate worktrees → join edge → pick |
| `fan_out` | Several independent nodes (any mode) → join when all required complete |

Prefer the smallest graph that fits. Default if unclear: one `in_session` node.

## Durable plan

Path: `<repo>/docs/plans/<slug>.md` (git-versionable).

1. Propose `plan_ref` + slug.
2. **Create or rewrite the graph only after owner OK** (🚧).
3. Later sessions: **append-only** node status + `## Log`. Do not reshape the graph
   without owner OK (trivial renames excepted).

### Plan file shape

```markdown
---
id: <slug>
goal: ""
status: active          # active | paused | done
created: YYYY-MM-DD
updated: YYYY-MM-DD
---

## Goal

<one paragraph>

## Graph

\`\`\`mermaid
flowchart LR
  ...
\`\`\`

## Nodes

| id | mode | status | note |
|----|------|--------|------|
| n1 | in_session | pending | ... |

Status values: `pending` | `running` | `done` | `blocked`

## Log

| timestamp | node | session | event |
|-----------|------|---------|-------|
| ISO8601 | n1 | <short> | created |
```

### Mermaid conventions

- `in_session` — rectangle `["label"]`
- `autonomous` — rounded `("label")`
- `parallel_hitl` — hexagon `{{"label"}}`
- Join/consume — dotted or labeled edges (`consume`, `blocks`)

Cite an entity-contract EDT activity id only if the owner already scoped one. Never invent EDT ids. Never mutate `contract.yaml`.

## Procedure

1. Read goal, cwd, existing `plan_ref` if any, touched files / open work.
2. Emit **header**.
3. Draft graph (Mermaid + Nodes table). Recommend one graph; offer numbered alternatives
   (this graph / all in_session / skip parallel_hitl / adjust).
4. On owner pick + OK for persistence → write/update `docs/plans/<slug>.md`, append Log.
5. Start only `ready_to_run` nodes. Do not spawn work before a pick.
6. As nodes finish, append Log and update the Nodes status column (append-only semantics).

## Agnosticism

- Do not name callers or sibling skills as prerequisites in the description. Do not
  name platforms or products in body text.
- No hardcoded instance paths, account emails, repo slugs, or timezones.
- Platform spawn/dispatch mechanics: follow the active harness playbook at runtime
  (issue + clean-context restart). Topology defines **mode**; the harness executes it.

## Don't

- Grill scope. Execute before a pick. Invent quality bars. Reshape the plan graph
  without owner OK. Treat joins as nodes. Hardcode who invokes this skill.
