#!/usr/bin/env bash
# Install or remove LaunchAgents for Secretary routines based on router config.
# ProgramArguments point at this package's run-routine.sh (not instance wrappers).
set -euo pipefail

# shellcheck source=_layout.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_layout.sh"

INSTANCE="${SECRETARY_INSTANCE:-$HOME/.secretary}"

if [[ -f "$INSTANCE/.env" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "$INSTANCE/.env"
  set +a
fi

# LaunchAgents must invoke *this* package. Prefer env/env-file SECRETARY_CORE only
# when it contains run-routine.sh; otherwise use the repo that owns this installer.
_PKG_CORE="$(cd "$ROUTINES_ROOT/../.." && pwd)"
if [[ -n "${SECRETARY_CORE:-}" && -f "${SECRETARY_CORE}/secretary/routines/run-routine.sh" ]]; then
  CORE="$(cd "$SECRETARY_CORE" && pwd)"
  if [[ "$CORE" != "$_PKG_CORE" ]]; then
    echo "WARN: SECRETARY_CORE=$CORE differs from installer package $_PKG_CORE — using env path." >&2
  fi
else
  if [[ -n "${SECRETARY_CORE:-}" && "$SECRETARY_CORE" != "$_PKG_CORE" ]]; then
    echo "WARN: SECRETARY_CORE=${SECRETARY_CORE} missing secretary/routines/run-routine.sh — using $_PKG_CORE" >&2
  fi
  CORE="$_PKG_CORE"
fi
export SECRETARY_CORE="$CORE"
# Re-bind layout roots to the resolved core (env may have pointed elsewhere).
export SECRETARY_ROUTINES_ROOT="$CORE/secretary/routines"
export ROUTINES_ROOT="$SECRETARY_ROUTINES_ROOT"
export ROUTINES_INVOKE="$ROUTINES_ROOT/invoke"
export ROUTINES_METRICS="$ROUTINES_ROOT/metrics"
export ROUTINES_OPS="$ROUTINES_ROOT/ops"
export ROUTINES_BACKFILL="$ROUTINES_ROOT/backfill"

MANIFEST="$INSTANCE/.cursor/routines/manifest.yaml"
LAUNCHD_DIR="$HOME/Library/LaunchAgents"
RUN_SCRIPT="$ROUTINES_ROOT/run-routine.sh"
LOG_DIR="$("$ROUTINES_ROOT/routines-log-dir.sh")"

if [[ ! -f "$RUN_SCRIPT" ]]; then
  echo "install-routine-schedule: missing $RUN_SCRIPT" >&2
  echo "  Set SECRETARY_CORE to a checkout that has secretary/routines/ (e.g. ~/Dev/secretary-core-main)." >&2
  echo "  Current SECRETARY_CORE=$CORE" >&2
  exit 127
fi

# shellcheck source=read-routine-config.sh
source "$ROUTINES_ROOT/read-routine-config.sh"

chmod +x "$RUN_SCRIPT" \
  "$ROUTINES_ROOT"/*.sh \
  "$ROUTINES_INVOKE"/* \
  "$ROUTINES_OPS"/* \
  "$ROUTINES_METRICS"/*.sh "$ROUTINES_METRICS"/*.py \
  "$ROUTINES_BACKFILL"/*.py 2>/dev/null || true

_uninstall_launchd() {
  python3 - "$MANIFEST" "$LAUNCHD_DIR" <<'PY'
import plistlib
import re
import sys
from pathlib import Path

manifest_path, launchd_dir = sys.argv[1:3]
text = Path(manifest_path).read_text()
ids = []
for line in text.splitlines():
    m = re.match(r"\s*-\s+id:\s+(\S+)", line)
    if m:
        ids.append(m.group(1))

launchd = Path(launchd_dir)
for rid in ids:
    label = f"com.alvaromur.secretary.routine.{rid}"
    plist = launchd / f"{label}.plist"
    if plist.exists():
        plist.unlink()
        print(f"removed {plist}")
    print(f"  launchctl bootout gui/$(id -u) {label} 2>/dev/null || true")
PY
}

if [[ "$ROUTINES_EXECUTOR" == "claude-scheduled" ]]; then
  echo "Router: claude-scheduled — local LaunchAgents are not used."
  echo "Schedule via Claude Code MCP scheduled-tasks (~/.claude/scheduled-tasks/*/SKILL.md)."
  echo ""
  echo "Removing any existing secretary routine LaunchAgents..."
  _uninstall_launchd
  echo ""
  echo "Done. Ensure Claude scheduled tasks are enabled and disable duplicates on other routers."
  exit 0
fi

if [[ "$ROUTINES_EXECUTOR" == "api-cron" ]]; then
  echo "Router: api-cron — installing LaunchAgents (invoke-api.sh → OpenAI-compatible HTTP)."
  API_KEY_VALUE="${!ROUTINES_API_KEY_ENV:-}"
  if [[ -z "$API_KEY_VALUE" && "$ROUTINES_API_KEY_ENV" != "OPENAI_API_KEY" ]]; then
    API_KEY_VALUE="${OPENAI_API_KEY:-}"
  fi
  if [[ -z "$API_KEY_VALUE" ]]; then
    echo "WARN: ${ROUTINES_API_KEY_ENV} is unset — LaunchAgents will fail until you export it and re-run this installer." >&2
  fi
elif [[ "$ROUTINES_EXECUTOR" == "cursor-cron" ]]; then
  echo "Router: cursor-cron — installing LaunchAgents (Cursor agent CLI)."
else
  echo "Unknown executor: $ROUTINES_EXECUTOR" >&2
  exit 2
fi

echo "ProgramArguments → $RUN_SCRIPT"
echo "SECRETARY_CORE=$CORE  SECRETARY_INSTANCE=$INSTANCE"

mkdir -p "$LOG_DIR"

python3 - "$MANIFEST" "$INSTANCE/.secretary.yml" "$LAUNCHD_DIR" "$RUN_SCRIPT" "$LOG_DIR" "$INSTANCE" "$CORE" "$ROUTINES_EXECUTOR" "$ROUTINES_MODEL" "$ROUTINES_API_KEY_ENV" "${API_KEY_VALUE:-}" <<'PY'
import plistlib
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

(
    manifest_path,
    config_path,
    launchd_dir,
    run_script,
    log_dir,
    instance,
    core,
    executor,
    model,
    api_key_env,
    api_key_value,
) = sys.argv[1:12]
text = Path(manifest_path).read_text()

disabled_cfg: set[str] = set()
if yaml and Path(config_path).is_file():
    cfg = yaml.safe_load(Path(config_path).read_text(encoding="utf-8")) or {}
    raw = ((cfg.get("dispatch") or {}).get("routines") or {}).get("disabled") or []
    if isinstance(raw, list):
        disabled_cfg = {str(x) for x in raw}

routines = []
current = None
for line in text.splitlines():
    m = re.match(r"\s*-\s+id:\s+(\S+)", line)
    if m:
        if current:
            routines.append(current)
        current = {"id": m.group(1), "enabled": True}
        continue
    if current is None:
        continue
    for key in ("cron",):
        m = re.match(rf"\s+{key}:\s+\"([^\"]+)\"", line)
        if m:
            current[key] = m.group(1)
            continue
    m = re.match(r"\s+enabled:\s+(true|false)", line, re.I)
    if m:
        current["enabled"] = m.group(1).lower() == "true"

if current:
    routines.append(current)

WEEKDAY_MAP = {"0": 0, "7": 0, "sun": 0, "mon": 1, "tue": 2, "wed": 3, "thu": 4, "fri": 5, "sat": 6}

runtime_map = {
    "cursor-cron": "cursor",
    "api-cron": "api",
    "claude-scheduled": "claude",
}


def parse_cron(cron: str) -> list[dict]:
    parts = cron.split()
    if len(parts) != 5:
        raise ValueError(f"unsupported cron: {cron}")
    minute_s, hour_s, _dom, _mon, dow_s = parts

    def expand(field: str, lo: int, hi: int) -> list[int]:
        if field == "*":
            return list(range(lo, hi + 1))
        out: list[int] = []
        for chunk in field.split(","):
            if "/" in chunk:
                base, step = chunk.split("/", 1)
                vals = expand(base, lo, hi)
                out.extend(vals[:: int(step)])
            elif chunk.isdigit():
                out.append(int(chunk))
            else:
                raise ValueError(f"unsupported cron field: {field}")
        return sorted(set(out))

    minutes = expand(minute_s, 0, 59)
    hours = expand(hour_s, 0, 23)

    intervals: list[dict] = []
    if dow_s != "*":
        weekdays = []
        for chunk in dow_s.split(","):
            if chunk.isdigit():
                weekdays.append(int(chunk))
            elif chunk.lower() in WEEKDAY_MAP:
                weekdays.append(WEEKDAY_MAP[chunk.lower()])
            else:
                raise ValueError(f"unsupported weekday: {chunk}")
        for wd in weekdays:
            for h in hours:
                for m in minutes:
                    intervals.append({"Hour": h, "Minute": m, "Weekday": wd})
    else:
        for h in hours:
            for m in minutes:
                intervals.append({"Hour": h, "Minute": m})
    return intervals


def plist_for(routine_id: str, cron: str) -> dict:
    intervals = parse_cron(cron)
    sci = intervals[0] if len(intervals) == 1 else intervals
    env = {
        "PATH": "/Users/alvaromur/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
        "SECRETARY_CORE": core,
        "SECRETARY_INSTANCE": instance,
        "SECRETARY_ROUTINES_EXECUTOR": executor,
        "SECRETARY_RUNTIME": runtime_map.get(executor, "cursor"),
        "SECRETARY_AGENT_MODEL": model,
        "ROUTINE_TRIGGER": "launchd",
    }
    if executor == "api-cron" and api_key_env:
        if api_key_value:
            env[api_key_env] = api_key_value
        else:
            env[api_key_env] = ""
    return {
        "Label": f"com.alvaromur.secretary.routine.{routine_id}",
        "ProgramArguments": [run_script, routine_id],
        "WorkingDirectory": instance,
        "EnvironmentVariables": env,
        "StandardOutPath": f"{log_dir}/launchd-{routine_id}.log",
        "StandardErrorPath": f"{log_dir}/launchd-{routine_id}.err.log",
        "StartCalendarInterval": sci,
    }


launchd = Path(launchd_dir)
launchd.mkdir(parents=True, exist_ok=True)

installed = []
for r in routines:
    rid = r["id"]
    cron = r.get("cron")
    plist_path = launchd / f"com.alvaromur.secretary.routine.{rid}.plist"
    if rid in disabled_cfg or r.get("enabled") is False:
        if plist_path.exists():
            plist_path.unlink()
            print(f"removed {plist_path} (disabled)")
        else:
            print(f"skip {rid}: disabled", file=sys.stderr)
        continue
    if not cron:
        print(f"skip {rid}: no cron", file=sys.stderr)
        continue
    with plist_path.open("wb") as f:
        plistlib.dump(plist_for(rid, cron), f)
    installed.append(rid)
    print(f"installed {plist_path}")

print(f"\n{len(installed)} plists written. Load with:")
for rid in installed:
    label = f"com.alvaromur.secretary.routine.{rid}"
    print(f"  launchctl bootout gui/$(id -u) {label} 2>/dev/null; launchctl bootstrap gui/$(id -u) {launchd}/com.alvaromur.secretary.routine.{rid}.plist")
PY

echo "Done. Reload changed agents with launchctl bootstrap (see above)."
