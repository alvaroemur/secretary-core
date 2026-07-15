#!/usr/bin/env bash
# Pre-brief pipeline — corre rutinas extractoras pendientes antes de secretary-briefing.
# Invocado desde run-routine.sh (salvo PRE_BRIEF_SKIP_PIPELINE=1).
#
# Modos:
#   normal (07:45): solo lo stale; correo vespertino NO (brief usa batch ayer 18:00).
#   PRE_BRIEF_FORCE=1: fuerza todas las rutinas matutinas (catch-up tras downtime).
set -euo pipefail

# shellcheck source=../_layout.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/_layout.sh"

INSTANCE="${SECRETARY_INSTANCE:-$HOME/.secretary}"
RUN_SCRIPT="$ROUTINES_ROOT/run-routine.sh"
REPO="${SECRETARY_REPO:-alvaroemur/cowork-secretary}"
LOG_DIR="$("$ROUTINES_ROOT/routines-log-dir.sh")"
TODAY="$(date '+%Y-%m-%d')"
DOW="$(date '+%u')" # 1=Mon … 7=Sun
FORCE="${PRE_BRIEF_FORCE:-0}"

mkdir -p "$LOG_DIR"
PIPE_LOG="$LOG_DIR/pre-brief-${TODAY}.log"
exec > >(tee -a "$PIPE_LOG") 2>&1

echo "[pre-brief] start $TODAY $(date '+%H:%M') force=$FORCE"

git -C "$INSTANCE" fetch origin -q 2>/dev/null || true

_yesterday() {
  date -v-1d '+%Y-%m-%d' 2>/dev/null || date -d 'yesterday' '+%Y-%m-%d'
}

_estado_date() {
  local path="$1"
  git -C "$INSTANCE" show "origin/main:${path}" 2>/dev/null \
    | grep -E '^(Última actualización|Fecha):' \
    | head -1 \
    | sed -E 's/^[^:]+:[[:space:]]*//' \
    | tr -d '\r' || true
}

_last_merge_prefix() {
  local prefix="$1"
  gh pr list --repo "$REPO" --state merged --limit 30 \
    --json headRefName,mergedAt \
    --jq -r --arg p "^${prefix}/" \
    '.[] | select(.headRefName | test($p)) | .mergedAt' 2>/dev/null \
    | head -1 | cut -c1-10
}

_open_auto_prefix() {
  local prefix="$1"
  gh pr list --repo "$REPO" --state open \
    --json headRefName,createdAt \
    --jq -r --arg p "^${prefix}/" \
    '.[] | select(.headRefName | test($p)) | .createdAt' 2>/dev/null \
    | wc -l | tr -d ' '
}

_run() {
  local id="$1" why="$2"
  echo "[pre-brief] → $id ($why)"
  if PRE_BRIEF_SKIP_PIPELINE=1 "$RUN_SCRIPT" "$id"; then
    echo "[pre-brief] ✓ $id"
  else
    local ec=$?
    echo "[pre-brief] ⚠ $id exit $ec (continúa pipeline)" >&2
  fi
}

# --- stale checks (return 0 = debe correr) ---

need_drive() {
  [[ "$FORCE" == "1" ]] && return 0
  local lm
  lm="$(_last_merge_prefix drive)"
  [[ -z "$lm" || "$lm" < "$TODAY" ]]
}

need_housekeeping() {
  [[ "$FORCE" == "1" ]] && return 0
  local lm opens
  lm="$(_last_merge_prefix housekeeping)"
  opens="$(_open_auto_prefix housekeeping)"
  [[ -z "$lm" || "$lm" < "$(_yesterday)" || "$opens" -gt 0 ]]
}

need_job_search() {
  [[ "$FORCE" == "1" ]] && return 0
  # L/M/X/J/V = 1,3,5 en manifest; solo esos días
  [[ "$DOW" =~ ^(1|3|5)$ ]] || return 1
  local lm
  lm="$(_last_merge_prefix job-search)"
  [[ -z "$lm" || "$lm" < "$(_yesterday)" ]]
}

need_correo() {
  [[ "$FORCE" == "1" ]] && return 0
  # Matutino: el brief necesita batch de ayer 18:00. Corre solo si main está más viejo.
  local ed yesterday
  ed="$(_estado_date extractors/mail/state.md)"
  yesterday="$(_yesterday)"
  [[ -n "$ed" && "$ed" < "$yesterday" ]]
}

need_reuniones() {
  [[ "$FORCE" == "1" ]] && return 0
  local lm opens
  lm="$(_last_merge_prefix reuniones)"
  opens="$(_open_auto_prefix reuniones)"
  # Transcripts nocturnos o PRs reuniones sin merge
  [[ -z "$lm" || "$lm" < "$TODAY" || "$opens" -gt 0 ]]
}

need_wiki() {
  [[ "${PRE_BRIEF_RUN_WIKI:-0}" == "1" ]] || return 1
  [[ "$FORCE" == "1" ]] && return 0
  local opens
  opens="$(_open_auto_prefix wiki)"
  [[ "$opens" -gt 0 ]]
}

# --- orden de dependencias (extractores → latido; brief lo dispara run-routine.sh) ---

if need_drive; then
  _run drive-crawler "stale drive"
else
  echo "[pre-brief] skip drive-crawler — fresh"
fi

if need_housekeeping; then
  _run housekeeping "stale housekeeping"
else
  echo "[pre-brief] skip housekeeping — fresh"
fi

if need_job_search; then
  _run job-search-crawler "día L/X/V o stale"
else
  echo "[pre-brief] skip job-search-crawler — fresh o no es L/X/V"
fi

if need_correo; then
  _run revision-correo "estado.md anterior a ayer (catch-up)"
else
  echo "[pre-brief] skip revision-correo — batch vespertino al día para el brief"
fi

if need_reuniones; then
  _run reuniones-update "reuniones stale o PRs abiertos"
else
  echo "[pre-brief] skip reuniones-update — fresh"
fi

if need_wiki; then
  _run wiki-update "PRE_BRIEF_RUN_WIKI o catch-up wiki"
else
  echo "[pre-brief] skip wiki-update — no solicitado (pesado; default 23:36)"
fi

echo "[pre-brief] → sec-heartbeat (pre-brief)"
HEARTBEAT_SLOT=pre-brief PRE_BRIEF_SKIP_PIPELINE=1 "$RUN_SCRIPT" sec-heartbeat || {
  echo "[pre-brief] ⚠ sec-heartbeat falló (¿main sucio?)" >&2
}

echo "[pre-brief] pipeline listo $(date '+%H:%M') — log: $PIPE_LOG"
