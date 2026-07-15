# secretary/routines — package layout (phase 1)

Engine-side home for scheduled-routine scripts formerly flat under
`$SECRETARY_INSTANCE/scripts/routines/`.

```
secretary/routines/
  _layout.sh                 # SECRETARY_* + ROUTINES_{INVOKE,METRICS,OPS,BACKFILL}
  run-routine.sh             # public entry (also wrapped in instance)
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

Instance keeps **thin wrappers** at the same filenames so LaunchAgents and docs
that call `~/.secretary/scripts/routines/run-routine.sh` keep working. Set
`SECRETARY_CORE` (default `~/Dev/secretary-core`).

Phase 2 (out of scope): `secretary routines run|install|metrics` CLI surface.
