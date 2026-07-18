---
name: sec-dream
description: Overnight completion loop — one substantial dream job per run (cross-signal synthesis → staged PR/draft), 05:00 Lima, ≤120 min budget
---

Read instance `CLAUDE.md` at `SECRETARY_INSTANCE` (resolve via `secretary config show` → `.instance` if the env var isn't set), then execute the operational skill at:

`~/.claude/skills/sec-dream/SKILL.md`

Follow that skill's phases, gates, and store contract (`subsystem/dream/`) exactly. Key reminders for this scheduled run:

- **Cadence:** start ~05:00 America/Lima, max 120 min wall clock, must finish before 07:00 portal aggregate / 07:10 heartbeat / 07:30 briefing. If the budget is exceeded, write a `blocked` / `timeout` status per the skill instead of continuing past the window.
- **Model:** this run executes natively as a Claude Code scheduled task — do not attempt to route through `dispatch.routines.api` (NanoGPT/minimax) or read `dispatch.routines.dream_model`; those apply to the api-cron executor, not this one.
- **One job per run.** Max one primary `dream_job`; `deferred_queue` max 3 — no parallel suggestions.
- **Gates:** PR create/update OK · Gmail draft OK (`gog`, never send) · merge **never** (surface merge-ready; owner runs `sec-merge` next session) · any soul/harness edit → worktree → PR, never direct push to `main`.
- Write outputs only under `subsystem/dream/` (`latest.json`, `dream-YYYYMMDD.json`, `log/YYYY-MM-DD.md`) per the skill's store contract.