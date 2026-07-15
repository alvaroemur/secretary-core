#!/usr/bin/env bash
# Append metrics.jsonl for poll/scheduler runs without an LLM harness.
# Reuses parse-routine-metrics.py --mechanical (same ledger schema as invoke-*.sh).
#
# usage: log-mechanical-routine.sh <routine_id> <outcome> <exit_code> [reason]
#   outcome: skip | ran | dry_run | error
#
# Env (set by caller at run start):
#   ROUTINE_RUN_STARTED_AT   ISO timestamp
#   ROUTINE_RUN_START_EPOCH  epoch seconds
#   ROUTINE_RUN_ID           optional; default <routine>-YYYY-MM-DD-HHMMSS
#   ROUTINE_TRIGGER          default launchd
set -euo pipefail

# shellcheck source=../_layout.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/_layout.sh"

ROUTINE_ID="${1:?routine_id}"
OUTCOME="${2:?outcome}"
EXIT_CODE="${3:?exit_code}"
REASON="${4:-}"

INSTANCE="${SECRETARY_INSTANCE:-$HOME/.secretary}"
# SCRIPT_DIR retired — use ROUTINES_* from _layout.sh
LOG_ROOT="$("$ROUTINES_ROOT/routines-log-dir.sh")"
METRICS_PY="$ROUTINES_METRICS/parse-routine-metrics.py"

TODAY="$(date '+%Y-%m-%d')"
TS="$(date '+%H%M%S')"
RUN_ID="${ROUTINE_RUN_ID:-${ROUTINE_ID}-${TODAY}-${TS}}"
STARTED_AT="${ROUTINE_RUN_STARTED_AT:-$(date -Iseconds)}"
START_EPOCH="${ROUTINE_RUN_START_EPOCH:-$(date +%s)}"
TRIGGER="${ROUTINE_TRIGGER:-launchd}"

RUN_DIR="$LOG_ROOT/runs/$TODAY"
mkdir -p "$RUN_DIR"

JSONL="$RUN_DIR/${RUN_ID}.jsonl"
LOG="$RUN_DIR/${RUN_ID}.log"
META="$RUN_DIR/${RUN_ID}.meta.json"
LEDGER="$LOG_ROOT/metrics.jsonl"

ENDED_AT="$(date -Iseconds)"
END_EPOCH=$(date +%s)
WALL_MS=$(( (END_EPOCH - START_EPOCH) * 1000 ))

ln -sf "$LOG" "$LOG_ROOT/latest-${ROUTINE_ID}.log"
ln -sf "$META" "$LOG_ROOT/latest-${ROUTINE_ID}.meta.json"

{
  echo "=== mechanical run: $RUN_ID ==="
  echo "started_at: $STARTED_AT"
  echo "routine_id: $ROUTINE_ID"
  echo "outcome: $OUTCOME"
  echo "trigger: $TRIGGER"
  [[ -n "$REASON" ]] && echo "reason: $REASON"
  echo "---"
} >>"$LOG" 2>/dev/null || true

python3 "$METRICS_PY" --mechanical \
  "$ROUTINE_ID" "$RUN_ID" "$STARTED_AT" "$ENDED_AT" "$EXIT_CODE" \
  "$OUTCOME" "$TRIGGER" "$REASON" \
  "$JSONL" "$LOG" "$META" "$LEDGER" "$WALL_MS" | tee -a "$LOG" || {
  echo "[log-mechanical-routine] WARN: metrics append failed" >&2
  exit 0
}
