#!/usr/bin/env bash
# extractor-freshness.sh — bloque ## Frescura extractoras para sec-heartbeat.
# Delega a `secretary fresh all --format markdown` cuando el CLI está disponible.
set -euo pipefail

# shellcheck source=../_layout.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/_layout.sh"

export SECRETARY_CORE="${SECRETARY_CORE:-$HOME/Dev/secretary-core}"
export SECRETARY_INSTANCE="${SECRETARY_INSTANCE:-$HOME/.secretary}"

if command -v secretary >/dev/null 2>&1; then
  exec secretary fresh all --format markdown
fi

if [[ -f "$SECRETARY_CORE/secretary/main.py" ]]; then
  exec env PYTHONPATH="$SECRETARY_CORE" python3 -m secretary.main fresh all --format markdown
fi

echo "Error: secretary CLI no disponible (pip install -e ~/Dev/secretary-core)" >&2
exit 1
