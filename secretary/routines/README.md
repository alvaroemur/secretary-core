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

## Preludio y cierre comunes (`ops/routine-pr.sh`)

Las rutinas que entregan un PR abren y cierran su corrida con un solo comando, sin repetir el bloque de worktree, commit, push y firma en cada playbook.

```bash
eval "$("$SECRETARY_CORE/secretary/routines/ops/routine-pr.sh" open --scope drive \
  --chain-label hilo:drive --chain-pattern '^drive/(auto|consolidado)-')"
# … la rutina escribe en "$WT" …
"$SECRETARY_CORE/secretary/routines/ops/routine-pr.sh" close --wt "$WT" --branch "$BRANCH" \
  --title "chore(drive): indexación diaria $(date +%F)" --body-file /tmp/pr-body.md \
  --routine drive-crawler --label hilo:drive --supersede "$PREV_PR"
```

- `open` imprime `WT`, `BRANCH`, `BASE` y `PREV_PR` para `eval`. Sin `--chain-pattern`, la base es `origin/main`.
- `close` firma el body con el helper de firma (`SECRETARY_SIGNATURE`), crea la label si falta y cierra el PR superado. Sin cambios, limpia y devuelve `RESULT=no-changes`. Si el push funcionó pero el PR falló, devuelve `RESULT=push-only` con código 3 y no revierte nada.
- `--dry-run` muestra los comandos sin efectos: sirve para las 3 corridas de validación.
- El worktree vive en `${ROUTINE_WT_ROOT:-/tmp}`, no en `$TMPDIR`.

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
