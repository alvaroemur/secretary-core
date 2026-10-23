#!/usr/bin/env bash
# sec-heartbeat-state.sh — estado determinista del latido en un archivo (n5, pieza 5).
#
# Uso:
#   sec-heartbeat-state.sh             sincroniza main de la instancia y escribe
#                                      subsystem/heartbeat/latest.md + state.json
#                                      con la sección "## Lectura" vacía
#   sec-heartbeat-state.sh --dry-run [--out DIR]
#                                      escribe latest.md + state.json en DIR
#                                      (default: $TMPDIR/sec-heartbeat-dry-run); no toca
#                                      subsystem/heartbeat/ ni hace git en la instancia
#   sec-heartbeat-state.sh --close     añade latest.md al diario YYYY-MM-DD.md,
#                                      commit y push a main (main-only, sin PR)
#
# Variables: HEARTBEAT_SLOT (pre-brief | q2h | close | on-demand), HEARTBEAT_SOURCE
# (scheduled | session). Contenido: inventario git/PR, tabla acc ↔ git con validación,
# delta, pendiente humano, calendario, brief y frescura de extractoras tal cual.
set -euo pipefail

# shellcheck source=../_layout.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/_layout.sh"

MODE=write
OUT_DIR=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) MODE=dry-run ;;
    --close)   MODE=close ;;
    --out)     OUT_DIR="${2:?--out requiere un directorio}"; shift ;;
    -h|--help) sed -n '2,19p' "$0"; exit 0 ;;
    *) echo "sec-heartbeat-state: argumento desconocido: $1" >&2; exit 2 ;;
  esac
  shift
done

REPO="$SECRETARY_INSTANCE"
HB_DIR="$REPO/subsystem/heartbeat"
TZ_CFG="$(secretary config get timezone 2>/dev/null || true)"
export TZ="${TZ:-${TZ_CFG:-UTC}}"

detect_slot() {
  local hour minute
  hour=$((10#$(date +%H)))
  minute=$((10#$(date +%M)))
  if [[ $hour -eq 7 && $minute -ge 5 && $minute -le 15 ]]; then echo pre-brief
  elif [[ ($hour -eq 22 || $hour -eq 0) && $minute -ge 5 && $minute -le 15 ]]; then echo close
  else echo on-demand
  fi
}
SLOT="${HEARTBEAT_SLOT:-$(detect_slot)}"

# ------------------------------------------------------------------ --close
if [[ "$MODE" == close ]]; then
  cd "$REPO"
  LATEST="$HB_DIR/latest.md"
  [[ -f "$LATEST" ]] || { echo "sec-heartbeat-state: falta $LATEST" >&2; exit 1; }
  if grep -q '<!-- lectura: pendiente' "$LATEST"; then
    echo "sec-heartbeat-state: la sección ## Lectura sigue vacía; escríbela antes de cerrar" >&2
    exit 1
  fi
  TS="$(sed -n 's/^- timestamp: \([0-9-]* [0-9:]*\).*/\1/p' "$LATEST" | head -1)"
  SLOT_FILE="$(sed -n 's/^- slot: //p' "$LATEST" | head -1)"
  [[ -n "$TS" ]] || { echo "sec-heartbeat-state: latest.md sin '- timestamp:'" >&2; exit 1; }
  DAY="${TS%% *}"
  HHMM="${TS##* }"
  {
    printf '\n## Latido %s (%s)\n\n' "$HHMM" "${SLOT_FILE:-$SLOT}"
    sed '1{/^# Heartbeat/d;}' "$LATEST"
  } >>"$HB_DIR/$DAY.md"
  git add subsystem/heartbeat/
  if ! git diff --cached --quiet; then
    git commit -m "chore(heartbeat): latido ${SLOT_FILE:-$SLOT} $TS"
  fi
  if ! git push origin main; then
    git pull --rebase origin main
    git push origin main
  fi
  echo "[sec-heartbeat-state] cerrado: $HB_DIR/$DAY.md + push a main"
  exit 0
fi

# ------------------------------------------------------------------ write / dry-run
if [[ "$MODE" == write ]]; then
  cd "$REPO"
  git fetch origin main
  git checkout main
  NON_HB="$("$ROUTINES_OPS/main-checkout-guard.sh" "$REPO" 2>/dev/null || true)"
  if [[ -n "$NON_HB" ]]; then
    echo "[sec-heartbeat-state] abort: main tiene cambios fuera de subsystem/heartbeat/:" >&2
    printf '%s\n' "$NON_HB" >&2
    exit 1
  fi
  if git status --porcelain subsystem/heartbeat/ | grep -q '^ M\|^M'; then
    git restore subsystem/heartbeat/ 2>/dev/null || git checkout -- subsystem/heartbeat/
  fi
  git pull --rebase origin main
  OUT_DIR="$HB_DIR"
  SOURCE="${HEARTBEAT_SOURCE:-scheduled}"
else
  OUT_DIR="${OUT_DIR:-${TMPDIR:-/tmp}/sec-heartbeat-dry-run}"
  SOURCE="dry-run"
fi
mkdir -p "$OUT_DIR"
# state.json previo: en write, el de subsystem/heartbeat/; en dry-run, el del dry-run anterior.
PREV_STATE="$OUT_DIR/state.json"

FRESH_FILE="$(mktemp)"
trap 'rm -f "$FRESH_FILE"' EXIT
if ! "$ROUTINES_OPS/extractor-freshness.sh" >"$FRESH_FILE" 2>&1; then
  printf '(extractor-freshness.sh falló)\n%s\n' "$(cat "$FRESH_FILE")" >"$FRESH_FILE.tmp"
  mv "$FRESH_FILE.tmp" "$FRESH_FILE"
fi

PYTHONPATH="$SECRETARY_CORE${PYTHONPATH:+:$PYTHONPATH}" python3 "$ROUTINES_OPS/heartbeat_state.py" \
  --out-dir "$OUT_DIR" --prev-state "$PREV_STATE" --freshness-file "$FRESH_FILE" \
  --slot "$SLOT" --source "$SOURCE"
