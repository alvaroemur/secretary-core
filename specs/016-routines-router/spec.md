---
id: "016"
slug: routines-router
layer: L0
status: fase 1
last_reviewed: 2026-07-27
implemented:
  - secretary/routines/run-routine.sh
  - secretary/routines/invoke/invoke-api-tool-loop.py
  - secretary/routines/install-routine-schedule.sh
  - $SECRETARY_INSTANCE/.secretary.yml
  - $SECRETARY_INSTANCE/.cursor/routines/manifest.yaml
  - $SECRETARY_INSTANCE/canon/operational/routines/executor.md
  - $SECRETARY_INSTANCE/canon/operational/routines/setup-manual.md
  - $SECRETARY_INSTANCE/canon/operational/routines/sec-refresh-harness.md
gaps:
  - ledger billing API por tool-call
  - tool loop como default (hoy opt-in)
---

# Spec — Feature 016: routines router (executor switch)

**Estado:** `fase 1` — executor `api-cron` activo; tool loop fase 1b opt-in; ledger billing pendiente  
**Branch:** `routines/016-api-cron-phase1`
**Capa (2026-07-27):** movido de L3-captura a L0-fundación — el scheduler corre *cualquier*
rutina (extractores, `wiki-update`, `housekeeping`, `sec-dream`, el briefing), no solo captura;
quedaba en L3 porque los primeros consumidores fueron extractores, no por ser infra de dominio.
**Migración de rutas (2026-07-27):** la implementación real vive en `secretary-core` desde el
refactor `34dc15ad` (2026-07-15); `$SECRETARY_INSTANCE/scripts/routines/` es solo fachada.

---

## Problem

Secretary routines can be triggered by **two schedulers at once**:

1. Claude Code MCP `scheduled-tasks` (cloud, Anthropic billing)
2. macOS LaunchAgents → `run-routine.sh` → Cursor `agent` CLI

Both fire the same playbooks (`~/.claude/scheduled-tasks/*/SKILL.md`), causing duplicate PRs and
double cost. There is no single config knob to declare which router is canonical.

A third path — **cron + direct LLM API** (no Cursor/Claude agent host) — is documented in
`secretary-core` getting-started but not wired in the instance.

## Decision

| Concern | Owner | Key |
|---------|-------|-----|
| Which router runs scheduled routines | `.secretary.yml` | `dispatch.routines.executor` |
| Default model for local invocations | `.secretary.yml` | `dispatch.routines.model` |
| Cron schedule + routine list | `.cursor/routines/manifest.yaml` | `routines[].cron` |
| Playbook procedure | `~/.claude/scheduled-tasks/<id>/SKILL.md` | unchanged |
| Dispatch issue executor allowlist | `.secretary.yml` | `dispatch.executor.repos` (separate) |

**Executor values:**

| Value | `SECRETARY_RUNTIME` | Scheduler | Invoke script |
|-------|---------------------|-----------|---------------|
| `claude-scheduled` | `claude` | MCP scheduled-tasks | `invoke-claude.sh` (manual/local fallback) |
| `cursor-cron` | `cursor` | LaunchAgents | `invoke-agent.sh` |
| `api-cron` | `api` | LaunchAgents | `invoke-api.sh` |

## Phase 0 (this PR)

- [x] `dispatch.routines` in `.secretary.yml`
- [x] `read-routine-config.sh` — YAML + env resolution
- [x] `run-routine.sh` branches on executor
- [x] `install-routine-schedule.sh` — install LaunchAgents for `cursor-cron`/`api-cron`; uninstall for `claude-scheduled`
- [x] `sec-heartbeat-orchestrator.sh` in-repo (router-aware)
- [x] `invoke-claude.sh`, `invoke-api.sh` (stub)
- [x] `canon/operational/routines/executor.md`
- [ ] `secretary config show` exposes `dispatch.routines` (engine PR)

## Phase 1

- [x] `invoke-api.sh` — OpenAI-compatible chat completions (`invoke-api-client.py`)
- [x] `dispatch.routines.api` (`base_url`, `api_key_env`) in `.secretary.yml`
- [x] `install-routine-schedule.sh` embeds API key env in LaunchAgent plists
- [x] Dedicated env var `SECRETARY_ROUTINES_API_KEY` (cron/routines only; separate from `NANOGPT_API_KEY`)
- [x] Auto-source `$SECRETARY_INSTANCE/.env` in `run-routine.sh` and `install-routine-schedule.sh`
- [x] `.env.example` committed; `.env` gitignored
- [x] HTTP tool loop (bash/gh/gog) — `invoke-api-tool-loop.py`; default `ROUTINES_API_TOOL_LOOP=1` (GitHub #428)
- [ ] Model pricing ledger for API billing mode
- [x] `sec-refresh` checklist: detect dual-scheduler misconfiguration — `canon/operational/routines/sec-refresh-harness.md` (#430)
- [ ] Optional: MCP helper to sync Claude scheduled-tasks crons from `manifest.yaml`

## Tool loop (phase 1b)

**Problem:** `invoke-api-client.py` is single-shot chat — routines need `gh`, `gog`, `secretary`, `git`.

**Contract:**

| Env | Default | Effect |
|-----|---------|--------|
| `ROUTINES_API_TOOL_LOOP` | `1` | `0` → single-shot `invoke-api-client.py` |
| `ROUTINES_API_TOOL_LOOP_MAX` | `30` | Max LLM↔tool iterations |
| `ROUTINES_API_SHELL_TIMEOUT` | `300` | Per-command timeout (seconds) |

**Tool:** `run_shell` — prefix allowlist: `gh`, `gog`, `secretary`, `git`, `python3`, `curl`, `jq`, read-only utils. No `;` chaining. Workspace = routine instance root.

**Smoke test:**

```bash
$SECRETARY_INSTANCE/scripts/routines/run-routine.sh sec-heartbeat
```

Manual: `canon/operational/routines/setup-manual.md` §6.

## Phase 2

- Export router docs to `secretary-core` getting-started
- Playbook English pass references `dispatch.routines` instead of hardcoded Cursor

## Success criteria

1. Changing one YAML key + re-running installer switches the active local scheduler.
2. `run-routine.sh <id>` respects config without editing scripts.
3. No duplicate routine runs when operator follows switch procedure in `canon/operational/routines/executor.md`.

## Out of scope

- Replacing playbooks or moving them into `.secretary/`
- Cursor Automations cloud worker (orthogonal to local cron)
- Merging `dispatch.executor` into `dispatch.routines` (different jobs: issue dispatch vs cron routines)
