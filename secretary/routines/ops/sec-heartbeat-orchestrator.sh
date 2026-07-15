#!/usr/bin/env bash
# sec-heartbeat — main-only orchestrator (no worktree, no PR).
# In-repo replacement for ~/.claude/scheduled-tasks/sec-heartbeat/run.sh
#
# Abort main-dirty: metrics.jsonl (blocker=main-dirty) + subsystem/heartbeat/blocker-main-dirty.json
# SessionStart (~/.claude/scripts/repos-sync-check.sh) ya muestra dirty en .secretary — no bloquea heartbeat explícitamente.
set -euo pipefail

# shellcheck source=../_layout.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/_layout.sh"

REPO="${SECRETARY_INSTANCE:-$HOME/.secretary}"
CORE="${SECRETARY_CORE:-$HOME/Dev/secretary-core}"
# SCRIPT_DIR retired — use ROUTINES_* from _layout.sh
PLAYBOOK="$HOME/.claude/scheduled-tasks/sec-heartbeat/SKILL.md"
ENTRY="$REPO/.cursor/routines/sec-heartbeat.md"
DRY_RUN="${DRY_RUN:-0}"

# shellcheck source=read-routine-config.sh
source "$ROUTINES_ROOT/read-routine-config.sh"

export SECRETARY_INSTANCE="$REPO"
export SECRETARY_CORE="$CORE"
export SECRETARY_AGENT_MODEL="$ROUTINES_MODEL"
export TZ="${TZ:-America/Lima}"

detect_slot() {
  local hour minute
  hour=$(date +%H | sed 's/^0//')
  minute=$(date +%M | sed 's/^0//')
  hour=${hour:-0}
  minute=${minute:-0}

  if [[ "$hour" -eq 7 && "$minute" -ge 5 && "$minute" -le 15 ]]; then
    echo "pre-brief"
  elif [[ "$hour" -eq 22 && "$minute" -ge 5 && "$minute" -le 15 ]]; then
    echo "close"
  elif [[ "$hour" -eq 0 && "$minute" -ge 5 && "$minute" -le 15 ]]; then
    echo "close"
  else
    # Invocación en sesión / hook post-reuniones sin HEARTBEAT_SLOT
    echo "on-demand"
  fi
}

SLOT="${HEARTBEAT_SLOT:-$(detect_slot)}"
TIMESTAMP="$(date '+%Y-%m-%d %H:%M')"

echo "[sec-heartbeat] slot=$SLOT runtime=$SECRETARY_RUNTIME executor=$ROUTINES_EXECUTOR timestamp=$TIMESTAMP repo=$REPO"

cd "$REPO"
git fetch origin main
git checkout main

GUARD="$ROUTINES_OPS/main-checkout-guard.sh"
NON_HB=""
if [[ -x "$GUARD" ]]; then
  NON_HB="$("$GUARD" "$REPO" 2>/dev/null || true)"
else
  DIRTY="$(git status --porcelain)"
  NON_HB="$(printf '%s\n' "$DIRTY" | grep -v '^??' | grep -v ' subsystem/heartbeat/' | grep -v '^$' || true)"
fi
if [[ -n "$NON_HB" ]]; then
  echo "[sec-heartbeat] abort: checkout has non-heartbeat dirty files:" >&2
  printf '%s\n' "$NON_HB" >&2

  LOG_ROOT="$("$ROUTINES_ROOT/routines-log-dir.sh")"
  LEDGER="$LOG_ROOT/metrics.jsonl"
  RUN_TS="$(date '+%Y-%m-%dT%H:%M:%S%z')"
  RUN_ID="sec-heartbeat-$(date '+%Y-%m-%d-%H%M%S')"
  mkdir -p "$LOG_ROOT"
  BLOCKER_PATHS_JSON="$(printf '%s\n' "$NON_HB" | python3 -c 'import json,sys; print(json.dumps([l.strip() for l in sys.stdin if l.strip()], ensure_ascii=False))')"
  python3 -c "
import json, sys
record = {
    'run_id': sys.argv[1],
    'routine_id': 'sec-heartbeat',
    'started_at': sys.argv[2],
    'ended_at': sys.argv[2],
    'exit_code': 1,
    'status': 'aborted',
    'blocker': 'main-dirty',
    'blocker_paths': json.loads(sys.argv[3]),
    'trigger': '${ROUTINE_TRIGGER:-cron}',
}
print(json.dumps(record, ensure_ascii=False))
" "$RUN_ID" "$RUN_TS" "$BLOCKER_PATHS_JSON" >>"$LEDGER"

  BLOCKER_NOTICE="$REPO/subsystem/heartbeat/blocker-main-dirty.json"
  python3 -c "
import json, sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
tz = ZoneInfo('America/Lima')
now = datetime.now(tz).isoformat(timespec='seconds')
payload = {
    'blocker': 'main-dirty',
    'detectedAt': now,
    'paths': json.loads(sys.argv[1]),
    'hint': 'wind-down Stage 3: mover a worktree, commit en PR, o restore/stash — main debe quedar limpio salvo subsystem/heartbeat/',
}
open(sys.argv[2], 'w', encoding='utf-8').write(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')
" "$BLOCKER_PATHS_JSON" "$BLOCKER_NOTICE"

  exit 1
fi
DIRTY="$(git status --porcelain)"
if [[ -f "$REPO/subsystem/heartbeat/blocker-main-dirty.json" ]]; then
  rm -f "$REPO/subsystem/heartbeat/blocker-main-dirty.json"
fi
if printf '%s\n' "$DIRTY" | grep -q ' subsystem/heartbeat/'; then
  git restore subsystem/heartbeat/ 2>/dev/null || git checkout -- subsystem/heartbeat/
fi

git pull --rebase origin main

if [[ "$DRY_RUN" == "1" ]]; then
  echo "[sec-heartbeat] DRY_RUN=1 — skipping agent, commit and push"
  exit 0
fi

FRESHNESS_SCRIPT="$ROUTINES_OPS/extractor-freshness.sh"
EXTRACTOR_FRESHNESS=""
if [[ -x "$FRESHNESS_SCRIPT" ]]; then
  EXTRACTOR_FRESHNESS="$("$FRESHNESS_SCRIPT" 2>&1)" || EXTRACTOR_FRESHNESS="(extractor-freshness.sh falló: $?)"
else
  EXTRACTOR_FRESHNESS="(extractor-freshness.sh no encontrado)"
fi

if [[ ! -f "$ENTRY" ]]; then
  echo "Missing entry point: $ENTRY" >&2
  exit 1
fi

PROMPT="$(cat <<EOF
Ejecuta la rutina sec-heartbeat completa.

Slot: $SLOT
Timestamp: $TIMESTAMP (America/Lima)
Playbook: $PLAYBOOK

Reglas duras:
- Escribe SOLO en subsystem/heartbeat/ (latest.md + YYYY-MM-DD.md append).
- Checkout main en $REPO — NO worktree, NO PR.
- Incluye en latest.md la sección ## Frescura extractoras **verbatim** (bloque precomputado abajo).
- Al terminar: git add subsystem/heartbeat/ && commit && push origin main.
- Mensaje de commit: chore(heartbeat): latido $SLOT $TIMESTAMP

## Frescura extractoras (precomputada — copiar verbatim)

$EXTRACTOR_FRESHNESS

$(cat "$ENTRY")
EOF
)"

chmod +x "$ROUTINES_INVOKE/invoke-agent.sh" "$ROUTINES_INVOKE/invoke-claude.sh" "$ROUTINES_INVOKE/invoke-api.sh" \
  "$ROUTINES_INVOKE/routine-stream-tee.py" "$ROUTINES_METRICS/parse-routine-metrics.py" 2>/dev/null || true

case "$ROUTINES_EXECUTOR" in
  claude-scheduled) INVOKE="$ROUTINES_INVOKE/invoke-claude.sh" ;;
  api-cron)         INVOKE="$ROUTINES_INVOKE/invoke-api.sh" ;;
  *)                INVOKE="$ROUTINES_INVOKE/invoke-agent.sh" ;;
esac

"$INVOKE" sec-heartbeat "$REPO" "$PROMPT"

INJECT_SCRIPT="$ROUTINES_OPS/inject-heartbeat-freshness.sh"
if [[ -x "$INJECT_SCRIPT" && -f "$REPO/subsystem/heartbeat/latest.md" ]]; then
  "$INJECT_SCRIPT" "$REPO/subsystem/heartbeat/latest.md" || true
fi

if git status --porcelain subsystem/heartbeat/ | grep -q .; then
  git add subsystem/heartbeat/
  git commit -m "chore(heartbeat): latido $SLOT $TIMESTAMP"
fi

if git status -sb | grep -q 'ahead'; then
  git push origin main
fi

echo "[sec-heartbeat] done slot=$SLOT"
