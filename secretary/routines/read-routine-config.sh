#!/usr/bin/env bash
# Read routines router config from .secretary.yml (or env override).
# Usage: source read-routine-config.sh
# Sets: ROUTINES_EXECUTOR, ROUTINES_MODEL, ROUTINES_API_BASE_URL,
#       ROUTINES_API_KEY_ENV, SECRETARY_RUNTIME
set -euo pipefail

# shellcheck source=_layout.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_layout.sh"

INSTANCE="${SECRETARY_INSTANCE:-$HOME/.secretary}"
CONFIG="$INSTANCE/.secretary.yml"

# Env overrides config file (useful for one-off runs and tests).
ROUTINES_EXECUTOR="${SECRETARY_ROUTINES_EXECUTOR:-}"
ROUTINES_MODEL="${SECRETARY_AGENT_MODEL:-}"
ROUTINES_API_BASE_URL="${ROUTINES_API_BASE_URL:-}"
ROUTINES_API_KEY_ENV="${ROUTINES_API_KEY_ENV:-}"

if [[ -z "$ROUTINES_EXECUTOR" && -f "$CONFIG" ]]; then
  read -r ROUTINES_EXECUTOR ROUTINES_MODEL_CFG ROUTINES_API_BASE_URL_CFG ROUTINES_API_KEY_ENV_CFG < <(
    python3 - "$CONFIG" "${ROUTINE_ID:-}" <<'PY'
import sys
import yaml
from pathlib import Path

cfg = yaml.safe_load(Path(sys.argv[1]).read_text(encoding="utf-8")) or {}
routines = (cfg.get("dispatch") or {}).get("routines") or {}
api = routines.get("api") or {}
routine_id = sys.argv[2] if len(sys.argv) > 2 else ""
overrides = routines.get("overrides") or {}
executor = overrides.get(routine_id) or routines.get("executor", "cursor-cron")
print(executor)
print(routines.get("model", "auto"))
print(api.get("base_url", "https://nano-gpt.com/api/v1"))
print(api.get("api_key_env", "SECRETARY_ROUTINES_API_KEY"))
PY
  )
  ROUTINES_MODEL="${ROUTINES_MODEL:-$ROUTINES_MODEL_CFG}"
  ROUTINES_API_BASE_URL="${ROUTINES_API_BASE_URL:-$ROUTINES_API_BASE_URL_CFG}"
  ROUTINES_API_KEY_ENV="${ROUTINES_API_KEY_ENV:-$ROUTINES_API_KEY_ENV_CFG}"
fi

if [[ -f "$CONFIG" && ( -z "${ROUTINES_MODEL}" || "${ROUTINES_MODEL}" == "auto" ) ]]; then
  ROUTINES_MODEL="$(python3 - "$CONFIG" <<'PYMODEL'
import sys, yaml
from pathlib import Path
cfg = yaml.safe_load(Path(sys.argv[1]).read_text(encoding="utf-8")) or {}
routines = (cfg.get("dispatch") or {}).get("routines") or {}
print(routines.get("model", "auto"))
PYMODEL
  )"
fi

ROUTINES_EXECUTOR="${ROUTINES_EXECUTOR:-cursor-cron}"
ROUTINES_MODEL="${ROUTINES_MODEL:-auto}"
ROUTINES_API_BASE_URL="${ROUTINES_API_BASE_URL:-https://nano-gpt.com/api/v1}"
ROUTINES_API_KEY_ENV="${ROUTINES_API_KEY_ENV:-SECRETARY_ROUTINES_API_KEY}"

case "$ROUTINES_EXECUTOR" in
  claude-scheduled) SECRETARY_RUNTIME=claude ;;
  cursor-cron)      SECRETARY_RUNTIME=cursor ;;
  api-cron)         SECRETARY_RUNTIME=api ;;
  *)
    echo "Unknown routines executor: $ROUTINES_EXECUTOR (expected claude-scheduled | cursor-cron | api-cron)" >&2
    exit 2
    ;;
esac

export ROUTINES_EXECUTOR ROUTINES_MODEL ROUTINES_API_BASE_URL ROUTINES_API_KEY_ENV SECRETARY_RUNTIME
