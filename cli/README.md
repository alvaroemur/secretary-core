# secretary CLI

Atomic operations for the secretary engine. Lives in `secretary-core/secretary/`; reads
the private **instance** via `SECRETARY_INSTANCE` (default `~/.secretary`) and `.secretary.yml`.

## Paradigm: atomic ops vs agentic skills

| Layer | What | Examples |
|-------|------|----------|
| **CLI (`secretary`)** | Deterministic, scriptable, no LLM | resolve paths, post status, run validators, grep memory |
| **Skills (`sec-*`)** | Agentic judgment, synthesis, guardrails | `sec-recall` synthesizes; `sec-write` decides destination |
| **Shell wrappers** | Back-compat aliases | `sec-status.sh` → `secretary status` when installed |

Skills should call CLI primitives for path resolution and mechanical steps, then apply
reasoning on top. Migración progresiva: cada script `.sh` que hace una cosa acotada puede
delegar al CLI y conservar fallback inline.

## Install

Requires **Python 3.11+**.

```bash
export SECRETARY_CORE=~/Dev/secretary-core
export SECRETARY_INSTANCE=~/.secretary
pip install -e ~/Dev/secretary-core
secretary --version
```

Without install (dev):

```bash
PYTHONPATH=~/Dev/secretary-core python3 -m secretary.main --help
```

Env vars:

- `SECRETARY_INSTANCE` — data root (`.secretary.yml`, extractores, memoria)
- `SECRETARY_CORE` — engine root (wiki build, future shared code)

## Commands (MVP)

```bash
secretary config show              # JSON: paths resolved absolute
secretary config show --yaml
secretary config path mail.memory  # → /Users/.../extractores/correo/memory

secretary paths                    # table of all path keys

secretary status "✅" "#1" "nota"  # comment on open brief (gh)
secretary validate                 # all CI validators
secretary validate wikilinks

secretary wiki build               # stages legacy layout → build.py → engine wiki/output

secretary recall <query>           # deterministic search (table)
secretary recall john --format json

secretary fresh mail                 # Paso 0 fresh-first (tabla)
secretary fresh meeting --format json
secretary fresh all --local          # incluye diff working vs main
secretary fresh all --format markdown  # bloque heartbeat
secretary modules list --format json
secretary modules health
secretary modules health --module mail --format json
secretary modules contract get job-search --format json

secretary acc fold acc-… pr:owner/repo#N

secretary core export-examples          # regen playbooks.example/ + skills.example/
secretary core export-examples --check  # CI/pre-commit: fail on drift (no writes)


secretary routines setup            # interactive router + LaunchAgent wizard
```

## Public/private example export

The engine keeps a public/private split: `playbooks/` and `skills/` are gitignored (the
**real**, private sources — real names, emails, Drive/Tactiq ids), while
`playbooks.example/` and `skills.example/` are the committed, **sanitized** copies that
`secretary/routines/setup.py` falls back to.

`secretary core export-examples` regenerates the `.example` dirs deterministically:

- Wipes and rebuilds `playbooks.example/` from `playbooks/` and `skills.example/` from
  `skills/`, so drift is impossible (examples = a pure function of sources + map).
- Applies the anonymization map to every **text** file (binaries copied verbatim).
- Never touches `docs/`, `README.md`, `CLAUDE.md`, `AGENTS.md`, or `CONTRIBUTING.md`
  (hand-authored prose).
- If a real source dir is missing it **stops** (exit 2) instead of writing garbage — so
  it is a local/pre-commit tool, not a CI step (CI has no private sources).
- `--check` regenerates into a temp area and diffs against the committed `.example` dirs,
  exiting non-zero on any difference. Use it as a pre-commit gate after editing the real
  playbooks/skills.

The substitution map is the single source of truth: `secretary/data/export_examples_map.yml`
(commented `redact:` + `preserve:` sections). Edit it — not the code — to change policy.

The CI **leak-guard** `scripts/ci/check_no_leaks.py` scans git-tracked files for the map's
`redact` patterns and fails if any sensitive literal survives (allowlisting `preserve`).
It runs in `.github/workflows/ci.yml` on every push/PR.

## Routines setup

`secretary routines setup` is the canonical entry for configuring `dispatch.routines`
(`claude-scheduled` | `cursor-cron` | `api-cron`), routine enable/disable, `.env` keys,
`install-routine-schedule.sh`, and LaunchAgent reload. Instance wrapper:
`~/.secretary/scripts/routines/setup.sh`.

Operator docs live in the instance: `operational/routines-executor.md`.

## Wiki build staging

`build.py` expects legacy top-level names (`wiki/`, `correo/`, …). The instance uses
`memoria/wiki/` and `extractores/`. `secretary wiki build` creates a temp directory with
symlinks, sets `SECRETARY_DATA` to it, and runs the engine builder — no instance mutation.

## Phase 2 (not in MVP)

- `secretary routines run <id>` — headless single-routine invoke
- `secretary heartbeat run` — invoke sec-heartbeat ingest headlessly
- `secretary dispatch list` — open dispatch issues across allowlist
- `secretary wiki serve` — wrapper over `wiki/serve.py`
- Config validation (`secretary config check`)
- `secretary fresh` wiki module · structured `--json` on remaining commands
