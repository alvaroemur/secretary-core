---
name: desk-overview
description: Show the state of the current project or repo set — work across sessions, pending decisions, mergeable PRs, dream deliveries, commitments and open briefs — with typed IDs, a one-line reply format to route each item, and paste-ready prompts.
---

# desk-overview

Read `../desk-context/references/control.md`. Observe and present: a query does not update
sources, publish, or start work. A later explicit owner reply can route items (see **Reply**).

Doctrine: `canon/rules/skills/skills-contract.md` § Output templates (T1). Output goes in the
owner's language; this template stays in English.

## Scope and sources

Run `secretary-desk overview --context <real-cwd>`. No argument: the session's context, not
the whole system. Inside a repo, use that project and all its worktrees; in a container, the
configured repos below it; with no match, state the coverage gap and inspect the current repo
with available tools without widening to every repo. Resolve managed worktrees through the
common repo. A project or repo argument fixes the scope.

The helper returns git, PRs, stashes, routine sources and decisions, with visible errors.
Stashes belong to the shared repo: count each once, not per worktree. Remote counters are
cached: fetch before claiming freshness. Missing data is not missing work.

Gather, for the scope:

| Source | How |
|--------|-----|
| Sessions | Harness session inventory (list/read threads or equivalent). Cross repo, checkout, branch, PR. A recent transcript does not prove a session is running. State coverage missing for other harnesses. Never message or interrupt other sessions. |
| Decisions | `secretary-desk decisions`, then read the original issue. Cross with state, recurrence and current policy; do not revive a blocker a later rule resolved. Include routine-usefulness decisions (exhausted sources, empty queues, strategy changes). |
| Mergeable PRs | Open PRs in scope that are mergeable with green or no required checks. |
| Dream deliveries | Open PRs whose head branch starts with `dream/`, in scope repos plus the instance; skip `chore(dream)` report PRs. Read each body for the commitment it advances and its verification step. |
| Commitments | `$(secretary config path meetings.memory)/acciones.md`: owner entries in scope with `estado: abierta`, overdue or due ≤7 days, and entries proposed to expire. |
| Briefs | `<cwd>/.briefs/*.md` and the instance `session.briefs` dir for this project: `status: pending` (or no `status` and ≤30 days old). Check whether the work already landed (merged PR, closed issue, commit on `origin/main`). |
| Signals | `secretary-desk signals` for routine reports in scope. |
| Daily brief | Latest brief of the local date and its sec-status comments. Cross progress with real evidence; a label, checkbox or open PR does not prove completion. |

## Session mode (decide first)

- **Ongoing session** (this conversation already has a topic, branch or files in flight):
  first line names the current topic. Items linked to it (same repo/branch/files/issue) go
  first and carry 🔗. Offer `aquí` only for linked items or quick ones (≤ a few tool calls).
  If an open dream PR touches files this session touches, raise ⚠️ overlap on the first lines.
- **Clean session** (nothing in flight): first line names the scope; order by urgency
  (blocked work and expiring decisions first, then mergeable, then the rest).

## IDs

Each actionable item gets a short ID by type, numbered per overview:

| Prefix | Type |
|--------|------|
| `D` | Decision the owner must take |
| `M` | Merge: PR ready to integrate (dream deliveries included) |
| `E` | Work in progress: session, worktree, branch, dirty tree, stash, blocker |
| `B` | Brief: pending continuity brief |
| `S` | Signal: routine health, coverage or commitment hygiene |

Print the legend once, in one line, right after the first line.

## Output

No fixed block list: include a section only when it has content, keep the order below, and
state empty coverage in **Coverage**. Emojis mark sections and state. Write plainly: no
"in simple terms", "in one sentence" or similar framing. The overview is complete, not short:
every actionable item appears with its ID.

Sections, in order:

1. **First line** — topic or scope (see Session mode), then the ID legend.
2. **⚠️ Overlap** — only in an ongoing session with overlap: dream PR, files, what to check.
3. **🧭 Requires your decision** — `D` items: evidence, cost of waiting, recommendation,
   link. Urgent first; postponed-not-due separate. With more than five, show five and count
   the rest with links.
4. **🔀 Ready to merge** — `M` items: PR, what it changes, checks, recommendation.
5. **🤖 Dream delivered** — one line per dream PR: `M<n>` · PR link · commitment it advances ·
   why it is useful · how to verify in <2 min. Omit the section when there are none.
6. **🛠️ In progress** — `E` items as a text tree (never Mermaid in chat), one node per
   worktree/session with a state mark:

   ```text
   <repo>
   ├─ E1 ✅ main — clean
   ├─ E2 🔄 <branch> — PR #<n>, 2 files dirty
   └─ E3 ⛔ <branch> — [gone] upstream, worktree left behind
   ```

   Marks: ✅ clean/done · 🔄 active · ⏳ waiting · ⛔ blocked or stale.
7. **📌 Briefs** — `B` items: file, date, what it resumes, `ya hecho`/`pendiente` with evidence.
8. **🗂️ Commitments** — overdue or due-soon owner commitments in scope (call them
   "compromisos" in the owner's language; IDs `acc-…` stay). Proposed expiries as `S`.
9. **📡 Signals and coverage** — `S` items, then what was checked, what was not, and when.
10. **▶️ Prompts** — see below.
11. **Reply block** — see below; always the last element.

## ▶️ Prompts

Only for items workable in another session (`sesión`, `agente`, `dream`); not for `D` items
the owner answers in chat. One fenced ```text block per item, no nested fences, headed by
its ID. Each prompt:

- Starts by checking whether the work is already done elsewhere (merged PR, closed issue,
  commit on `origin/main`, another session's branch) and stops with a report if it is.
- Names repo, absolute paths readable by any agent, branch policy and the done condition.
- Never references scratchpad, `/tmp` or a harness worktree.

## Reply

Every item routes with RUN-1: `<ID>: aquí | sesión | agente | dream`.

- `aquí` — this session does it now.
- `sesión` — launch a new session with its prompt. Several `sesión` lines launch in parallel
  (harness session tool when available; otherwise hand back the prompts to paste).
- `agente` — a subagent in this session; the result comes back here.
- `dream` — append the item to the dream queue (`$(secretary config path subsystem.dream)/queue.md`
  § Pendientes, FIFO, format in that file's header). Dream still evaluates it before acting.

End with one prefilled reply block in ```text, the recommendation per ID, ready to copy and
edit. `D` items take a short answer instead (`D1: sí`, `D2: opción 2`). Numbers or keywords
alone also work (`M1 M2: aquí`).

```text
D1: <recommended answer>
M1: aquí
E2: sesión
B1: dream
```

The query alone does not authorize execution. Record postponements on the issue with a signed
comment only when the owner asks.
