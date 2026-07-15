#!/usr/bin/env bash
# Direct LLM API invocation for scheduled routines (api-cron router).
# Phase 1: OpenAI-compatible chat completions (NanoGPT and similar).
# Uso: invoke-api.sh <routine_id> <workspace> <prompt>
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

# shellcheck source=read-routine-config.sh
source "$ROUTINES_ROOT/read-routine-config.sh"

AGENT_MODEL="${ROUTINES_MODEL:-${SECRETARY_AGENT_MODEL:-auto}}"
API_CLIENT="$ROUTINES_INVOKE/invoke-api-client.py"
API_TOOL_LOOP="$ROUTINES_INVOKE/invoke-api-tool-loop.py"
USE_TOOL_LOOP="${ROUTINES_API_TOOL_LOOP:-1}"
STREAM_TEE="$ROUTINES_INVOKE/routine-stream-tee.py"
METRICS_PY="$ROUTINES_METRICS/parse-routine-metrics.py"

API_KEY="${!ROUTINES_API_KEY_ENV:-}"
if [[ -z "$API_KEY" && "$ROUTINES_API_KEY_ENV" != "OPENAI_API_KEY" ]]; then
  API_KEY="${OPENAI_API_KEY:-}"
fi

RUN_DIR="$LOG_ROOT/runs/$TODAY"
mkdir -p "$RUN_DIR"

JSONL="$RUN_DIR/${RUN_ID}.jsonl"
LOG="$RUN_DIR/${RUN_ID}.log"
META="$RUN_DIR/${RUN_ID}.meta.json"
PROMPT_FILE="$RUN_DIR/${RUN_ID}.prompt.txt"
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
  echo "runtime: api"
  echo "model: $AGENT_MODEL"
  echo "api_base_url: $ROUTINES_API_BASE_URL"
  echo "api_key_env: $ROUTINES_API_KEY_ENV"
  echo "trigger: $TRIGGER"
  echo "workspace: $WORKSPACE"
  echo "---"
} | tee "$LOG"

if [[ -z "$API_KEY" ]]; then
  echo "Missing API key: set ${ROUTINES_API_KEY_ENV} (or OPENAI_API_KEY) in env or LaunchAgent plist." >&2
  exit 127
fi

if [[ "$USE_TOOL_LOOP" == "1" ]]; then
  if [[ ! -f "$API_TOOL_LOOP" ]]; then
    echo "Missing API tool loop: $API_TOOL_LOOP" >&2
    exit 127
  fi
  API_RUNNER="$API_TOOL_LOOP"
  API_RUNNER_ARGS=("$ROUTINES_API_BASE_URL" "$API_KEY" "$AGENT_MODEL" "$PROMPT_FILE" "$JSONL" "$WORKSPACE")
else
  if [[ ! -f "$API_CLIENT" ]]; then
    echo "Missing API client: $API_CLIENT" >&2
    exit 127
  fi
  API_RUNNER="$API_CLIENT"
  API_RUNNER_ARGS=("$ROUTINES_API_BASE_URL" "$API_KEY" "$AGENT_MODEL" "$PROMPT_FILE" "$JSONL")
fi

printf '%s' "$PROMPT" >"$PROMPT_FILE"
: >"$JSONL"

{
  echo "tool_loop: $USE_TOOL_LOOP"
} | tee -a "$LOG"

export SECRETARY_RUN_ID="$RUN_ID"
export SECRETARY_ROUTINE_ID="$ROUTINE_ID"
export SECRETARY_SIGNATURE_CONTEXT="${SECRETARY_SIGNATURE_CONTEXT:-$ROUTINE_ID}"
export SECRETARY_MODEL="$AGENT_MODEL"
export SECRETARY_BRANCH="$(git -C "$WORKSPACE" branch --show-current 2>/dev/null || true)"

set +e
cd "$WORKSPACE"
python3 "$API_RUNNER" "${API_RUNNER_ARGS[@]}" 2>&1 | tee -a "$LOG"
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
