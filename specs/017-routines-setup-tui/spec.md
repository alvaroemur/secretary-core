---
id: "017"
slug: routines-setup-tui
layer: L0
status: implementado
last_reviewed: 2026-07-02
implemented:
  - secretary/routines/setup.py
  - $SECRETARY_INSTANCE/scripts/routines/setup.sh
---

# Spec — Feature 017: routines setup wizard

**Estado:** `implementado` — CLI canónico `secretary routines setup` (v2 stdlib; rich TUI fuera de alcance)  
**Branch:** `routines/cli-setup-canonical`
**Capa (2026-07-27):** movido de L3-captura a L0-fundación junto con 016 — es el wizard de
setup del scheduler genérico, no de un extractor puntual.

---

## Problem

Switching the routines router (`claude-scheduled` | `cursor-cron` | `api-cron`) requires editing
`.secretary.yml`, ensuring `.env` has the API key, running `install-routine-schedule.sh`, and
manually reloading LaunchAgents. Easy to misconfigure dual schedulers or forget disabled routines.

## Solution

Interactive wizard in **secretary-core** CLI:

```bash
secretary routines setup
```

Instance thin wrapper: `scripts/routines/setup.sh` → `exec secretary routines setup`.

Implementation: `secretary-core/secretary/routines/setup.py` (stdlib + PyYAML).

### Flow

1. Mode — new setup | update existing
2. Optional `git fetch origin main`
3. Executor choice — `claude-scheduled` | `cursor-cron` | `api-cron` (shows current)
4. Executor-specific options:
   - `api-cron`: base URL, model, confirm `api_key_env` (never print key; prompt to edit `.env`)
   - `cursor-cron`: model for `agent` CLI
   - `claude-scheduled`: remind to disable LaunchAgents; enable MCP scheduled-tasks UI
5. Routines from `manifest.yaml` — enable/disable (persisted as `dispatch.routines.disabled`)
6. Preview `dispatch.routines` block
7. Apply YAML merge (preserve other keys), ensure `.env.example`, run installer
8. Offer LaunchAgent bootout/bootstrap (skipped for `claude-scheduled`)
9. MCP note — disable Claude scheduled-tasks when not on `claude-scheduled`
10. Optional `validate_ordenamiento` / `contract_health`

### Config surface (additive)

```yaml
dispatch:
  routines:
    executor: cursor-cron   # claude-scheduled | cursor-cron | api-cron
    model: auto
    disabled:   # optional — routine ids skipped by install-routine-schedule.sh
      - whatsapp-monitor
    api:        # api-cron only
      base_url: https://nano-gpt.com/api/v1
      api_key_env: SECRETARY_ROUTINES_API_KEY
```

Manifest may also set per-routine `enabled: false` (installer respects both).

## Success criteria

1. Idempotent — safe to re-run on same instance.
2. No API keys in stdout, commits, or logs.
3. `install-routine-schedule.sh` skips/removes plists for disabled routines.
4. Docs point to `secretary routines setup` as canonical entry.
5. All three executors remain supported; instance `run-routine.sh` keeps invoke-claude / invoke-agent / invoke-api branches.

## Out of scope

- Rich/curses TUI (v2)
- MCP sync of Claude scheduled-tasks crons from manifest
- Modifying cron expressions (manifest remains source for schedule)
- Removing `claude-scheduled` or `cursor-cron` router paths

## Related

- Spec 016: routines router
- `canon/operational/routines/executor.md`
- Engine: `cli/README.md` → `secretary routines setup`
