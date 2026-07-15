#!/usr/bin/env bash
# Resuelve el directorio de logs de rutinas (subsystem/routines).
# Fuente: .secretary.yml → paths.subsystem.routines
set -euo pipefail

# shellcheck source=_layout.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_layout.sh"

INSTANCE="${SECRETARY_INSTANCE:-$HOME/.secretary}"
CORE="${SECRETARY_CORE:-$HOME/Dev/secretary-core}"

_resolve_from_config() {
  if command -v secretary >/dev/null 2>&1; then
    secretary config path subsystem.routines 2>/dev/null && return 0
    secretary config path operations.routines 2>/dev/null && return 0
  fi
  if [[ -f "$CORE/secretary/config.py" ]]; then
    PYTHONPATH="$CORE" python3 -c "
from secretary.config import resolve_path_key
for key in ('subsystem.routines', 'operations.routines'):
    try:
        print(resolve_path_key(key))
        break
    except KeyError:
        pass
" 2>/dev/null && return 0
  fi
  return 1
}

_migrate_legacy() {
  local new_dir="$1"
  local old_dir="$INSTANCE/extractors/mail/logs/routines"
  [[ -e "$old_dir" ]] || return 0
  [[ -L "$old_dir" ]] && return 0

  mkdir -p "$new_dir"
  if [[ -d "$old_dir" ]]; then
    # Merge sin sobrescribir artefactos existentes en destino
    if command -v rsync >/dev/null 2>&1; then
      rsync -a "$old_dir"/ "$new_dir"/
    else
      cp -Rn "$old_dir"/. "$new_dir"/ 2>/dev/null || true
    fi
    rm -rf "$old_dir"
  fi
  mkdir -p "$INSTANCE/extractors/mail/logs"
  ln -sf "../../../subsystem/routines" "$old_dir"
}

LOG_DIR="$(_resolve_from_config || echo "$INSTANCE/subsystem/routines")"
_migrate_legacy "$LOG_DIR"
mkdir -p "$LOG_DIR"
# Compat: paths.mail.logs → symlink a subsystem/routines (spec 012)
mkdir -p "$INSTANCE/extractors/mail/logs"
_compat="$INSTANCE/extractors/mail/logs/routines"
[[ -L "$_compat" || -e "$_compat" ]] || ln -sf "../../../subsystem/routines" "$_compat"
printf '%s\n' "$LOG_DIR"
