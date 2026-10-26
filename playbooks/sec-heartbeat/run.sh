#!/usr/bin/env bash
# sec-heartbeat — comando único del estado determinista del latido (main-only, sin PR).
#
#   run.sh             sincroniza main y escribe subsystem/heartbeat/latest.md + state.json
#   run.sh --dry-run   escribe en un directorio temporal; no toca subsystem/heartbeat/ ni git
#   run.sh --close     añade latest.md al diario, commit y push a main
#
# Lógica en secretary-core: secretary/routines/ops/sec-heartbeat-state.sh.
# La sesión ejecuta este archivo; no lo lee ni repite sus pasos a mano.
set -euo pipefail

CORE="${SECRETARY_CORE:-$(secretary config get core_path 2>/dev/null || true)}"
CORE="${CORE:-$HOME/Dev/secretary-core}"
CORE="${CORE/#\~/$HOME}"

exec "$CORE/secretary/routines/ops/sec-heartbeat-state.sh" "$@"
