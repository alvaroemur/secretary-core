#!/usr/bin/env bash
# reuniones-scheduler — ligero, sin LLM.
# Poll (launchd) en ventana laboral: mira calendario, dispara reuniones-update
# solo si hay evento(s) que terminaron hace ~30–90 min y scout ve docs nuevas
# (o scout ausente / ambiguo → avanza con cautela).
#
# Exit codes (cron/launchd — no-cero solo en error real):
#   0  skip o disparo completado (ver log: STATUS=skip|ran|dry-run)
#   1  error (gog/calendar/runtime / reuniones-update falló)
set -euo pipefail

# shellcheck source=../_layout.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/_layout.sh"

INSTANCE="${SECRETARY_INSTANCE:-$HOME/.secretary}"
CORE="${SECRETARY_CORE:-$HOME/Dev/secretary-core}"
# SCRIPT_DIR retired — use ROUTINES_* from _layout.sh
RUN_SCRIPT="$ROUTINES_ROOT/run-routine.sh"
SCOUT="$ROUTINES_OPS/reuniones-scout.sh"
REPO="${SECRETARY_REPO:-alvaroemur/cowork-secretary}"
STATE_DIR="$INSTANCE/extractors/meetings/memory"
STATE_FILE="$STATE_DIR/_scheduler_seen.json"
TZ_NAME="${TZ:-America/Lima}"

# Ventana Tactiq post-reunión (minutos desde end)
WINDOW_MIN_MIN="${REUNIONES_SCHEDULER_WINDOW_MIN:-30}"
WINDOW_MAX_MIN="${REUNIONES_SCHEDULER_WINDOW_MAX:-90}"
# No relanzar si hay PR reuniones/* creado hace menos de N minutos
PR_COOLDOWN_MIN="${REUNIONES_SCHEDULER_PR_COOLDOWN_MIN:-45}"
DRY_RUN="${REUNIONES_SCHEDULER_DRY_RUN:-0}"
FORCE="${REUNIONES_SCHEDULER_FORCE:-0}"

export SECRETARY_INSTANCE="$INSTANCE"
export SECRETARY_CORE="$CORE"
export TZ="$TZ_NAME"

if [[ -f "$INSTANCE/.env" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "$INSTANCE/.env"
  set +a
fi

mkdir -p "$STATE_DIR"
chmod +x "$SCOUT" "$RUN_SCRIPT" "$ROUTINES_INVOKE/log-mechanical-routine.sh" 2>/dev/null || true

log() { printf '[reuniones-scheduler] %s\n' "$*"; }

TODAY="$(date '+%Y-%m-%d')"
TS="$(date '+%H%M%S')"
export ROUTINE_RUN_ID="reuniones-scheduler-${TODAY}-${TS}"
export ROUTINE_RUN_STARTED_AT="$(date -Iseconds)"
export ROUTINE_RUN_START_EPOCH=$(date +%s)
export ROUTINE_TRIGGER="${ROUTINE_TRIGGER:-launchd}"

_finish() {
  local outcome="$1" exit_code="${2:-0}" reason="${3:-}"
  if [[ -x "$ROUTINES_INVOKE/log-mechanical-routine.sh" ]]; then
    "$ROUTINES_INVOKE/log-mechanical-routine.sh" reuniones-scheduler "$outcome" "$exit_code" "$reason" || true
  fi
  exit "$exit_code"
}

PERSONAL_ACCOUNT=""
if command -v secretary >/dev/null 2>&1; then
  PERSONAL_ACCOUNT="$(
    secretary config show 2>/dev/null \
      | python3 -c 'import json,sys
try:
  d=json.load(sys.stdin)
  print(((d.get("accounts") or {}).get("personal") or "").strip())
except Exception:
  pass' 2>/dev/null || true
  )"
fi
if [[ -z "$PERSONAL_ACCOUNT" && -f "$INSTANCE/.secretary.yml" ]]; then
  PERSONAL_ACCOUNT="$(
    python3 -c 'import sys
try:
  import yaml
except ImportError:
  sys.exit(0)
from pathlib import Path
cfg=yaml.safe_load(Path(sys.argv[1]).read_text()) or {}
print(((cfg.get("accounts") or {}).get("personal") or "").strip())
' "$INSTANCE/.secretary.yml" 2>/dev/null || true
  )"
fi
GOG_ACCOUNT_FLAG=()
if [[ -n "$PERSONAL_ACCOUNT" ]]; then
  GOG_ACCOUNT_FLAG=(--account="$PERSONAL_ACCOUNT")
fi

_recent_reuniones_pr() {
  command -v gh >/dev/null 2>&1 || return 1
  local created_at
  created_at="$(
    gh pr list --repo "$REPO" --state open --limit 20 \
      --json headRefName,createdAt \
      --jq '[.[] | select(.headRefName | test("^reuniones/")) | .createdAt] | sort | reverse | .[0] // empty' 2>/dev/null || true
  )"
  [[ -z "$created_at" ]] && return 1
  export RS_PR_CREATED="$created_at"
  export RS_PR_COOLDOWN="$PR_COOLDOWN_MIN"
  python3 - <<'PY'
from datetime import datetime, timezone
import os
created = datetime.fromisoformat(os.environ["RS_PR_CREATED"].replace("Z", "+00:00"))
age_min = (datetime.now(timezone.utc) - created.astimezone(timezone.utc)).total_seconds() / 60.0
raise SystemExit(0 if age_min <= float(os.environ["RS_PR_COOLDOWN"]) else 1)
PY
}

_calendar_candidates() {
  if ! command -v gog >/dev/null 2>&1; then
    log "ERROR: gog not found"
    return 1
  fi

  local cal_json
  set +e
  if [[ ${#GOG_ACCOUNT_FLAG[@]} -gt 0 ]]; then
    cal_json="$(gog calendar events primary --from=today --to=tomorrow --max=50 --json "${GOG_ACCOUNT_FLAG[@]}" 2>&1)"
  else
    cal_json="$(gog calendar events primary --from=today --to=tomorrow --max=50 --json 2>&1)"
  fi
  local gog_exit=$?
  set -e
  if [[ $gog_exit -ne 0 ]]; then
    log "ERROR: gog calendar failed (exit $gog_exit)"
    printf '%s\n' "$cal_json" >&2
    return 1
  fi

  export RS_CAL_JSON="$cal_json"
  export RS_WINDOW_MIN="$WINDOW_MIN_MIN"
  export RS_WINDOW_MAX="$WINDOW_MAX_MIN"
  export RS_STATE_FILE="$STATE_FILE"
  export RS_FORCE="$FORCE"
  python3 - <<'PY'
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

tz = ZoneInfo(os.environ.get("TZ", "America/Lima"))
now = datetime.now(tz)
wmin = int(os.environ["RS_WINDOW_MIN"])
wmax = int(os.environ["RS_WINDOW_MAX"])
force = os.environ.get("RS_FORCE", "0") == "1"
state_path = Path(os.environ["RS_STATE_FILE"])

seen = {}
if state_path.is_file():
    try:
        seen = (json.loads(state_path.read_text(encoding="utf-8")) or {}).get("triggered") or {}
    except json.JSONDecodeError:
        seen = {}

raw = os.environ.get("RS_CAL_JSON", "")
try:
    data = json.loads(raw)
except json.JSONDecodeError:
    print("PARSE_ERROR", file=sys.stderr)
    sys.exit(3)

events = data.get("events") if isinstance(data, dict) else data
if not isinstance(events, list):
    events = []

candidates = []
for ev in events:
    if not isinstance(ev, dict):
        continue
    eid = str(ev.get("id") or "")
    if not eid or eid in seen:
        continue
    end = ev.get("end") or {}
    if "dateTime" not in end:
        continue  # all-day
    status = (ev.get("status") or "").lower()
    if status == "cancelled":
        continue
    declined = False
    for a in ev.get("attendees") or []:
        if isinstance(a, dict) and a.get("self") and (a.get("responseStatus") or "").lower() == "declined":
            declined = True
            break
    if declined:
        continue
    try:
        et = datetime.fromisoformat(end["dateTime"])
        if et.tzinfo is None:
            et = et.replace(tzinfo=tz)
        et_local = et.astimezone(tz)
    except ValueError:
        continue
    age_min = (now - et_local).total_seconds() / 60.0
    if not force and not (wmin <= age_min <= wmax):
        continue
    if force and age_min < 0:
        continue
    title = (ev.get("summary") or "(sin título)").replace("\n", " ")[:80]
    candidates.append(
        {
            "id": eid,
            "summary": title,
            "ended_at": et_local.isoformat(timespec="seconds"),
            "age_min": round(age_min, 1),
        }
    )

candidates.sort(key=lambda c: c["age_min"])
print(json.dumps({"now": now.isoformat(timespec="seconds"), "candidates": candidates}, ensure_ascii=False))
PY
}

_mark_triggered() {
  local eid="$1" summary="$2" ended_at="$3" result="$4"
  export RS_STATE_FILE="$STATE_FILE"
  export RS_EID="$eid"
  export RS_SUMMARY="$summary"
  export RS_ENDED="$ended_at"
  export RS_RESULT="$result"
  python3 - <<'PY'
import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

path = Path(os.environ["RS_STATE_FILE"])
tz = ZoneInfo(os.environ.get("TZ", "America/Lima"))
now = datetime.now(tz).isoformat(timespec="seconds")
data: dict = {"triggered": {}}
if path.is_file():
    try:
        data = json.loads(path.read_text(encoding="utf-8")) or data
    except json.JSONDecodeError:
        pass
trig = data.setdefault("triggered", {})
trig[os.environ["RS_EID"]] = {
    "summary": os.environ.get("RS_SUMMARY", ""),
    "ended_at": os.environ.get("RS_ENDED", ""),
    "triggered_at": now,
    "result": os.environ.get("RS_RESULT", "ran"),
}
cutoff = datetime.now(tz).timestamp() - 14 * 86400
pruned = {}
for k, v in trig.items():
    ts = v.get("triggered_at") or ""
    try:
        t = datetime.fromisoformat(ts).timestamp()
    except ValueError:
        t = cutoff
    if t >= cutoff:
        pruned[k] = v
data["triggered"] = pruned
path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY
}

log "start $(date '+%Y-%m-%d %H:%M') force=$FORCE dry_run=$DRY_RUN window=${WINDOW_MIN_MIN}-${WINDOW_MAX_MIN}m"

if ! CAND_JSON="$(_calendar_candidates)"; then
  log "ERROR: calendar fetch failed"
  _finish error 1 "gog calendar failed"
fi
if [[ -z "$CAND_JSON" ]] || ! printf '%s' "$CAND_JSON" | jq -e . >/dev/null 2>&1; then
  log "ERROR: calendar parse failed"
  _finish error 1 "calendar parse failed"
fi

N_CAND="$(printf '%s' "$CAND_JSON" | jq -r '.candidates | length')"
if [[ "${N_CAND:-0}" -eq 0 ]]; then
  log "STATUS=skip — no calendar candidates in ${WINDOW_MIN_MIN}–${WINDOW_MAX_MIN}m window"
  _finish skip 0 "no calendar candidates in ${WINDOW_MIN_MIN}-${WINDOW_MAX_MIN}m window"
fi

log "candidates=$N_CAND"
printf '%s' "$CAND_JSON" | jq -r '.candidates[] | "  - \(.id) | \(.age_min)m | \(.summary)"'

if _recent_reuniones_pr; then
  log "STATUS=skip — open reuniones/* PR within last ${PR_COOLDOWN_MIN}m"
  _finish skip 0 "open reuniones/* PR within last ${PR_COOLDOWN_MIN}m"
fi

if [[ -f "$SCOUT" && "${REUNIONES_SCHEDULER_SKIP_SCOUT:-0}" != "1" ]]; then
  set +e
  "$SCOUT"
  SCOUT_EXIT=$?
  set -e
  if [[ $SCOUT_EXIT -eq 0 ]]; then
    log "STATUS=skip — scout: no new Tactiq docs (candidates stay unmarked for retry)"
    _finish skip 0 "scout: no new Tactiq docs"
  fi
  if [[ $SCOUT_EXIT -ne 2 ]]; then
    log "WARN: scout exit $SCOUT_EXIT — proceeding cautiously"
  fi
else
  log "scout missing or skipped — proceeding"
fi

if [[ "$DRY_RUN" == "1" ]]; then
  log "STATUS=dry-run — would invoke run-routine.sh reuniones-update"
  _finish dry_run 0 "would invoke reuniones-update"
fi

log "→ run-routine.sh reuniones-update (REUNIONES_SCOUT_SKIP=1)"
set +e
REUNIONES_SCOUT_SKIP=1 \
  ROUTINE_TRIGGER="${ROUTINE_TRIGGER:-reuniones-scheduler}" \
  "$RUN_SCRIPT" reuniones-update
RUN_EXIT=$?
set -e

if [[ $RUN_EXIT -eq 0 ]]; then
  while IFS=$'\t' read -r eid sum ended; do
    [[ -z "$eid" ]] && continue
    _mark_triggered "$eid" "$sum" "$ended" "ran"
  done < <(printf '%s' "$CAND_JSON" | jq -r '.candidates[] | [.id, .summary, .ended_at] | @tsv')
  log "STATUS=ran — reuniones-update exit 0; marked $N_CAND candidate(s)"
  _finish ran 0 "reuniones-update ok; marked ${N_CAND} candidate(s)"
fi

log "ERROR: reuniones-update exit $RUN_EXIT (candidates not marked)"
_finish error 1 "reuniones-update exit ${RUN_EXIT}"
