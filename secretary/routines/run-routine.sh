#!/usr/bin/env bash
# Secretary routine runner — dispatches to the configured router/executor.
set -euo pipefail

ROUTINE_ID="${1:?usage: run-routine.sh <routine-id>}"

# shellcheck source=_layout.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_layout.sh"

if [[ -f "$INSTANCE/.env" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "$INSTANCE/.env"
  set +a
fi

ENTRY="$INSTANCE/.cursor/routines/${ROUTINE_ID}.md"
PLAYBOOK="$HOME/.claude/scheduled-tasks/${ROUTINE_ID}/SKILL.md"

# shellcheck source=read-routine-config.sh
source "$ROUTINES_ROOT/read-routine-config.sh"

export SECRETARY_INSTANCE="$INSTANCE"
export SECRETARY_CORE="$CORE"
export SECRETARY_AGENT_MODEL="$ROUTINES_MODEL"
# Passthrough para secretary-briefing modo refresh (sec-refresh Fase 5)
export BRIEF_REFRESH_ISSUE="${BRIEF_REFRESH_ISSUE:-}"
export BRIEF_REFRESH_VIA="${BRIEF_REFRESH_VIA:-}"

# sec-heartbeat: main-only orchestrator (never worktree, never PR)
if [[ "$ROUTINE_ID" == "sec-heartbeat" ]]; then
  exec "$ROUTINES_OPS/sec-heartbeat-orchestrator.sh"
fi

# Poll ligero (sin LLM): calendario → scout → opcionalmente reuniones-update
if [[ "$ROUTINE_ID" == "reuniones-scheduler" ]]; then
  exec "$ROUTINES_OPS/reuniones-scheduler.sh"
fi

# Briefing: extractoras pendientes → latido pre-brief → brief
if [[ "$ROUTINE_ID" == "secretary-briefing" && "${PRE_BRIEF_SKIP_PIPELINE:-0}" != "1" ]]; then
  "$ROUTINES_OPS/pre-brief-pipeline.sh"
fi

if [[ ! -f "$ENTRY" ]]; then
  echo "Missing entry point: $ENTRY" >&2
  exit 1
fi

if [[ ! -f "$PLAYBOOK" ]]; then
  echo "Missing playbook: $PLAYBOOK" >&2
  exit 1
fi

# reuniones-update: scout TACTIQ_ROOT before LLM spend
if [[ "$ROUTINE_ID" == "reuniones-update" && "${REUNIONES_SCOUT_SKIP:-0}" != "1" ]]; then
  SCOUT="$ROUTINES_OPS/reuniones-scout.sh"
  if [[ -f "$SCOUT" ]]; then
    chmod +x "$SCOUT" 2>/dev/null || true
    set +e
    "$SCOUT"
    SCOUT_EXIT=$?
    set -e
    if [[ $SCOUT_EXIT -eq 0 ]]; then
      echo "[run-routine] reuniones-scout: no-op — skipping agent"
      exit 0
    fi
  fi
fi

REFRESH_NOTE=""
if [[ "$ROUTINE_ID" == "secretary-briefing" && -n "${BRIEF_REFRESH_ISSUE:-}" ]]; then
  REFRESH_NOTE="
Modo refresh activo: BRIEF_REFRESH_ISSUE=${BRIEF_REFRESH_ISSUE} — actualizar issue existente (gh issue edit), NO crear nuevo ni cerrar briefs.
BRIEF_REFRESH_VIA=${BRIEF_REFRESH_VIA:-secretary-briefing}
"
fi

PROMPT="$(cat <<EOF
Ejecuta la rutina ${ROUTINE_ID} completa siguiendo el playbook.

Playbook: $PLAYBOOK
Runtime: $SECRETARY_RUNTIME (executor: $ROUTINES_EXECUTOR)
${REFRESH_NOTE}
$(cat "$ENTRY")
EOF
)"

cd "$INSTANCE"
chmod +x "$ROUTINES_INVOKE/invoke-agent.sh" "$ROUTINES_INVOKE/invoke-claude.sh" "$ROUTINES_INVOKE/invoke-api.sh" \
  "$ROUTINES_INVOKE/invoke-api-client.py" "$ROUTINES_INVOKE/invoke-api-tool-loop.py" \
  "$ROUTINES_INVOKE/routine-stream-tee.py" "$ROUTINES_METRICS/parse-routine-metrics.py" \
  "$ROUTINES_OPS/resolve-routine-pr.sh" \
  "$ROUTINES_OPS/reuniones-scheduler.sh" "$ROUTINES_OPS/reuniones-scout.sh" \
  "$ROUTINES_INVOKE/log-mechanical-routine.sh" 2>/dev/null || true

case "$ROUTINES_EXECUTOR" in
  claude-scheduled) INVOKE="$ROUTINES_INVOKE/invoke-claude.sh" ;;
  api-cron)         INVOKE="$ROUTINES_INVOKE/invoke-api.sh" ;;
  *)                INVOKE="$ROUTINES_INVOKE/invoke-agent.sh" ;;
esac

set +e
"$INVOKE" "$ROUTINE_ID" "$INSTANCE" "$PROMPT"
INVOKE_EXIT=$?
set -e

# Tras reuniones-update exitoso (agente corrió; scout no-op ya salió arriba):
# latido post-reuniones. Evita recursión y solapa con close 22:10.
if [[ "$ROUTINE_ID" == "reuniones-update" && $INVOKE_EXIT -eq 0 \
  && "${REUNIONES_POST_HEARTBEAT:-1}" != "0" \
  && "${HEARTBEAT_FROM_REUNIONES:-0}" != "1" ]]; then
  HOUR_NOW="$(TZ="${TZ:-America/Lima}" date +%H | sed 's/^0//')"
  HOUR_NOW="${HOUR_NOW:-0}"
  if [[ "$HOUR_NOW" -ge 8 && "$HOUR_NOW" -le 21 ]]; then
    echo "[run-routine] post-reuniones → sec-heartbeat (slot=post-reuniones)"
    set +e
    HEARTBEAT_SLOT=post-reuniones \
      HEARTBEAT_FROM_REUNIONES=1 \
      ROUTINE_TRIGGER="${ROUTINE_TRIGGER:-post-reuniones}" \
      "$ROUTINES_ROOT/run-routine.sh" sec-heartbeat
    HB_EXIT=$?
    set -e
    if [[ $HB_EXIT -ne 0 ]]; then
      echo "[run-routine] WARN: post-reuniones heartbeat exit $HB_EXIT (¿main-dirty?)" >&2
    fi
  else
    echo "[run-routine] post-reuniones heartbeat skipped (hour=$HOUR_NOW; close 22:10 covers night)"
  fi
fi

exit "$INVOKE_EXIT"
