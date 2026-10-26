---
name: topology
description: >-
  Design a multi-agent work graph for scoped work: nodes in three modes (in_session,
  autonomous, parallel_hitl), joins as edges, optional named subgraph patterns
  (gauntlet, bake_off, fan_out). Persists a durable plan under docs/plans/ (or
  instance `_diseño/plans/`) that sessions update together. Default progress surface:
  Mermaid in the plan plus a re-emitted text tree with node status in chat; optional
  harness canvas or minimal interactive HTML. Triggers: "/topology",
  "how should we run this", "work graph", "multi-agent layout". NOT for locking
  scope or writing continuation prompts alone.
user-invocable: true
---

# topology — work-graph execution design

Design **how** scoped work runs across agents and sessions. Output is a **work graph**
plus an optional durable plan file — not a single global strategy menu.

Doctrine: `canon/rules/skills/skills-contract.md` (§ Output templates)

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
**plan_ref:** <docs/plans/<slug>.md | _diseño/plans/<slug>.md | none>
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

Path (git-versionable):

- Work repos (Cowork / Dev): `<repo>/docs/plans/<slug>.md`
- Secretary instance: `_diseño/plans/<slug>.md` (root `docs/` is denylisted)

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
- **Status on the drawing** (plan file only, optional): put status in the node label
  (`n1<br/>done`) and/or `classDef` for `done` | `running` | `pending` | `blocked`,
  without rewriting edges. The chat projection is the text tree (see Progress surfaces);
  its marks map ✅ done · 🔄 running · ⏳ pending · ⛔ blocked.

Cite an entity-contract EDT activity id only if the owner already scoped one. Never invent EDT ids. Never mutate `contract.yaml`.

## Progress surfaces

How the owner **sees** the graph advance. Source of truth remains the plan file
(Nodes + Log + Graph). Surfaces are projections.

### Default (always)

1. **Mermaid lives only in the plan** under `## Graph` (structural graph). Some harnesses
   do not render Mermaid in chat, so chat never carries it.
2. **In chat**, the graph goes as an indented text tree with one status mark per node:
   ✅ done · ⏳ pending · 🔄 running · ⛔ blocked. Children are the nodes an edge leads to;
   label the edge after the arrow when it is not obvious (`→ merge`, `→ consume`).

   ```text
   n6 ⏳ integration (in_session)
   ├─ ← merge  n1 🔄 F1 dream (parallel_hitl)
   ├─ ← merge  n2 ✅ F2 commitments (parallel_hitl)
   └─ ← merge  n5 ⛔ F5 cross-check (autonomous) — waiting on owner
   ```

3. **During execution**, after each material node status change (or at a sensible batch
   join), re-emit the tree with fresh marks. Same node ids and edges. Do not wait until the
   whole graph finishes. Keep it short: no Log dump; point to `plan_ref` for history.
4. **Pick block:** when the owner must choose a graph or route nodes, end with one fenced
   ```text block, prefilled, using the common reply format
   `<node>: aquí | sesión | agente | dream` (or the numbered option). No nested fences.

### Optional (harness-dependent)

Prefer the cheapest surface that the harness already provides:

| Priority | When | What |
|----------|------|------|
| 1 | Harness has a **native canvas / side-panel** app surface | Offer or refresh a canvas that embeds nodes + statuses (and optionally a DAG). Link it; do not paste the full React source into chat. |
| 2 | No canvas available | **Offer** a **minimal** interactive HTML in-transcript artifact (progress + node pick → one-line detail). Owner can decline. |

**HTML budget (hard):** few tokens. Allowed: progress bar, compact node buttons or chips, one detail line, tiny legend. Forbidden: full DAG redraw in HTML, long scripts, duplicated Nodes tables, prose essays inside the fragment. If the HTML would rival the text tree in size, skip HTML.

Do not require canvas or HTML to run the graph. Do not invent a third durable file format for progress — update the plan; project to surfaces.

## Procedure

1. Read goal, cwd, existing `plan_ref` if any, touched files / open work.
2. Emit **header**.
3. Draft graph (text tree in chat + Nodes table; Mermaid goes to the plan). Recommend one
   graph; offer numbered alternatives (this graph / all in_session / skip parallel_hitl /
   adjust) and close with the pick block.
4. On owner pick + OK for persistence → write/update the plan file under
   `docs/plans/` or `_diseño/plans/`, append Log.
5. Start only `ready_to_run` nodes. Do not spawn work before a pick.
6. As nodes finish, append Log and update the Nodes status column (append-only semantics).
   **Re-emit** the text tree with status. Optionally refresh canvas or
   offer minimal HTML per **Progress surfaces**.
7. When the graph completes (or pauses), one final text tree + plan status update.

## Agnosticism

- Do not name callers or sibling skills as prerequisites in the description. Do not
  name platforms or products in body text.
- No hardcoded instance paths, account emails, repo slugs, or timezones.
- Platform spawn/dispatch mechanics: follow the active harness playbook at runtime
  (issue + clean-context restart). Topology defines **mode**; the harness executes it.
- Progress surfaces may use harness capabilities (canvas, in-transcript HTML) without
  naming the product; fall back to the text tree when those are absent.

## Don't

- Grill scope. Execute before a pick. Invent quality bars. Reshape the plan graph
  without owner OK. Treat joins as nodes. Hardcode who invokes this skill.
- Dump full canvas source or large HTML into chat. Paste Mermaid in chat. Skip the text
  tree because a richer surface exists. Require canvas/HTML to proceed.
