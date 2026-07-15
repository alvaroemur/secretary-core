# secretary/routines — package layout (phase 1)

Engine-side home for scheduled-routine scripts formerly flat under
`$SECRETARY_INSTANCE/scripts/routines/`.

```
secretary/routines/
  _layout.sh                 # SECRETARY_* + ROUTINES_{INVOKE,METRICS,OPS,BACKFILL}
  run-routine.sh             # public entry (LaunchAgents ProgramArguments)
  read-routine-config.sh
  install-routine-schedule.sh
  routines-log-dir.sh
  setup.sh                   # → `secretary routines setup`
  setup.py                   # CLI setup wizard (existing)
  invoke/                    # harnesses + stream tee + mechanical log
  metrics/                   # parse/report + pricing + api_usage
  ops/                       # heartbeat, reuniones, pre-brief, guards, publish
  backfill/                  # historical metrics / wallet helpers
```

## LaunchAgents

`install-routine-schedule.sh` writes plists whose `ProgramArguments` invoke
**this package’s** `run-routine.sh` (absolute path expanded at install time).
Each plist also sets `EnvironmentVariables`:

- `SECRETARY_CORE` — absolute path of the core checkout used at install
- `SECRETARY_INSTANCE` — instance root (default `~/.secretary`)

Resolve `SECRETARY_CORE` from (in order): process env, optional
`$SECRETARY_INSTANCE/.env`, else the repo that contains this file (`_layout.sh`).
If `run-routine.sh` is missing, the installer exits 127 with a clear message
(typical cause: `~/Dev/secretary-core` checked out to a feature branch without
this package — use a `main` worktree, e.g. `~/Dev/secretary-core-main`).

## Instance facade

The instance keeps at most `scripts/routines/README.md` + optional `setup.sh`
(`secretary routines setup`). Do not rely on instance wrappers for cron.

Phase 2 (out of scope): `secretary routines run|install|metrics` CLI surface.
