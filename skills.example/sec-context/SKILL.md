---
name: sec-context
description: >-
  Assemble and inject deterministic session context, rules, active skills, routines, and work map on the fly. Triggers: "/sec-context", "assemble context", "contexto de sesion", "inyectar reglas", "refresh agent context", "dame el mapa de trabajo".
user-invocable: true
---

# sec-context

**Mission:** assemble and inject the fresh deterministic context, work map, available skills, scheduled routines, and active rules into any agent session on demand, mitigating stale static AGENTS.md files.

## Guardrails
- **Read only** — never mutate repo files, worktrees, or remote state.
- **Deterministic** — use `secretary context` as the single source of truth; never invent rules or skills.

## Loop
1. Execute `secretary context --format markdown --cwd "$(pwd)"` to collect the complete, live system context.
2. Read the host repository context, identifying the current active plane (`Cowork`, `Dev`, `Secretary`), branch, and clean/dirty state.
3. If specific sections are requested, filter via `--section` (`doctrine`, `taxonomy`, `skills`, `routines`, `git`, `host`).
4. Output the structured briefing so the session immediately aligns with active doctrine, skills, and schedules.

## Report
Render the assembled context directly in the session so the agent is immediately calibrated to the owner's language, anti-slop guidelines, folder layout, active skills, and routines.

Use judgment on the detail; don't enumerate every case. Anything invariant about
the user (language, git conventions, what's private, folder layout) lives in the
runtime's CLAUDE.md, not here. Current-moment data comes from the runtime (the
engine's lookup sources), not this file.
