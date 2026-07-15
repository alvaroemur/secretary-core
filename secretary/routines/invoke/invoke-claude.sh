#!/usr/bin/env bash
# Invokes Claude Code CLI for a scheduled routine (claude-scheduled router).
# Uso: invoke-claude.sh <routine_id> <workspace> <prompt>
set -euo pipefail

# shellcheck source=../_layout.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/_layout.sh"

ROUTINE_ID="${1:?routine_id}"
WORKSPACE="${2:?workspace}"
PROMPT="${3:?prompt}"

INSTANCE="${SECRETARY_INSTANCE:-$HOME/.secretary}"
# SCRIPT_DIR retired — use ROUTINES_* from _layout.sh
LOG_ROOT="$("$ROUTINES_ROOT/routines-log-dir.sh")"
TODAY="$(date '+%Y-%m-%d')"
TS="$(date '+%H%M%S')"
RUN_ID="${ROUTINE_ID}-${TODAY}-${TS}"
TRIGGER="${ROUTINE_TRIGGER:-manual}"

AGENT_MODEL="${ROUTINES_MODEL:-${SECRETARY_AGENT_MODEL:-auto}}"
STREAM_TEE="$ROUTINES_INVOKE/routine-stream-tee.py"
METRICS_PY="$ROUTINES_METRICS/parse-routine-metrics.py"

RUN_DIR="$LOG_ROOT/runs/$TODAY"
mkdir -p "$RUN_DIR"

JSONL="$RUN_DIR/${RUN_ID}.jsonl"
LOG="$RUN_DIR/${RUN_ID}.log"
META="$RUN_DIR/${RUN_ID}.meta.json"
LEDGER="$LOG_ROOT/metrics.jsonl"

STARTED_AT="$(date -Iseconds)"
START_EPOCH=$(date +%s)

ln -sf "$LOG" "$LOG_ROOT/latest-${ROUTINE_ID}.log"
ln -sf "$JSONL" "$LOG_ROOT/latest-${ROUTINE_ID}.jsonl"
ln -sf "$META" "$LOG_ROOT/latest-${ROUTINE_ID}.meta.json"

{
  echo "=== routine run: $RUN_ID ==="
  echo "started_at: $STARTED_AT"
  echo "routine_id: $ROUTINE_ID"
  echo "runtime: claude"
  echo "model: $AGENT_MODEL"
  echo "trigger: $TRIGGER"
  echo "workspace: $WORKSPACE"
  echo "---"
} | tee "$LOG"

if ! command -v claude >/dev/null 2>&1; then
  echo "claude CLI not found — install Claude Code or set PATH" >&2
  exit 127
fi

export SECRETARY_RUN_ID="$RUN_ID"
export SECRETARY_ROUTINE_ID="$ROUTINE_ID"
export SECRETARY_SIGNATURE_CONTEXT="${SECRETARY_SIGNATURE_CONTEXT:-$ROUTINE_ID}"
export SECRETARY_MODEL="$AGENT_MODEL"
export SECRETARY_BRANCH="$(git -C "$WORKSPACE" branch --show-current 2>/dev/null || true)"

set +e
cd "$WORKSPACE"
# Claude Code non-interactive; stream-json when supported, else plain tee.
claude -p \
  --verbose \
  --model "$AGENT_MODEL" \
  --add-dir "$WORKSPACE" \
  --add-dir "$HOME/Dev/secretary-core" \
  --output-format stream-json \
  "$PROMPT" 2>&1 | python3 "$STREAM_TEE" "$JSONL" | tee -a "$LOG"
AGENT_EXIT=$?
set -e

ENDED_AT="$(date -Iseconds)"
END_EPOCH=$(date +%s)
WALL_MS=$(( (END_EPOCH - START_EPOCH) * 1000 ))

# shellcheck source=resolve-routine-pr.sh
source "$ROUTINES_OPS/resolve-routine-pr.sh" "$ROUTINE_ID" "$LOG" "$WORKSPACE" || true

python3 "$METRICS_PY" \
  "$ROUTINE_ID" "$RUN_ID" "$STARTED_AT" "$ENDED_AT" "$AGENT_EXIT" \
  "$AGENT_MODEL" "$TRIGGER" \
  "$JSONL" "$LOG" "$META" "$LEDGER" "$WALL_MS" | tee -a "$LOG"

{
  echo "---"
  echo "ended_at: $ENDED_AT"
  echo "wall_ms: $WALL_MS"
  echo "exit_code: $AGENT_EXIT"
  echo "artifacts: log=$LOG jsonl=$JSONL meta=$META"
} | tee -a "$LOG"

exit "$AGENT_EXIT"
