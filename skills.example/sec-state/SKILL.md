---
name: sec-state
description: Show the live state of work in progress — what's running, what's dirty, what's blocked. Use when a session needs to answer "where did I leave things?" or when starting a new session and wanting situational awareness.
---

# sec-state

**Mission:** surface the current work-in-progress state from secretary's wip store so any session can orient itself instantly.

## Guardrails
- **Read only** — never modify wip files or repo state; only observe.
- Don't infer status from repos directly (stale data risk) — read the wip store; if it's empty, say so clearly.

## Loop
1. Read `.secretary.yml` to resolve the wip store path.
2. List all wip entries (one file per repo/context). For each: title, status, last-updated, open threads.
3. If a wip entry references a branch or PR, note its name — don't fetch remote status unless asked.
4. Synthesize: which repos are actively dirty, which have a parked thread, which have nothing tracked.

## Report
Render **inline**. Header: `🧭 **Estado** · <N> repos activos`. One bullet per active entry, prefixed by a status flag — 🟢 ok/active · 🟡 needs attention/parked · 🔴 blocked/urgent — with branch/PR and dirty count. Close with a `→` suggested-action line if something stands out. If the wip store is empty, say so and suggest a `sec-write` pass to park current state.

Use judgment on the detail; don't enumerate every case. Anything invariant about
the user (language, git conventions, what's private, folder layout) lives in the
runtime's CLAUDE.md, not here. Current-moment data comes from the runtime (the
engine's lookup sources), not this file.
