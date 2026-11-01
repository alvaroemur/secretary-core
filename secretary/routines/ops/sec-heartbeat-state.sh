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
#                                      commit y push a main (sin PR) desde un worktree
#                                      efímero de origin/main: el checkout principal
#                                      puede tener cambios ajenos y no se toca
#
# Fallos: cada corrida write/close que sale con error suma al contador
# $XDG_STATE_HOME/secretary/heartbeat-fallos; desde el 2.º fallo seguido deja un 🚫
# en el brief (secretary status). Un --close exitoso lo reinicia.
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
    -h|--help) sed -n '2,25p' "$0"; exit 0 ;;
    *) echo "sec-heartbeat-state: argumento desconocido: $1" >&2; exit 2 ;;
  esac
  shift
done

REPO="$SECRETARY_INSTANCE"
HB_DIR="$REPO/subsystem/heartbeat"
FAIL_FILE="${XDG_STATE_HOME:-$HOME/.local/state}/secretary/heartbeat-fallos"
FRESH_FILE=""
CLOSE_WT=""

heartbeat_exit() {
  local rc=$?
  trap - EXIT
  [[ -n "$FRESH_FILE" ]] && rm -f "$FRESH_FILE" "$FRESH_FILE.tmp"
  if [[ -n "$CLOSE_WT" ]]; then
    git -C "$REPO" worktree remove --force "$CLOSE_WT" >/dev/null 2>&1 || true
    rm -rf "$(dirname "$CLOSE_WT")"
  fi
  [[ "$MODE" == dry-run ]] && exit "$rc"
  mkdir -p "$(dirname "$FAIL_FILE")" 2>/dev/null || exit "$rc"
  if [[ $rc -eq 0 ]]; then
    [[ "$MODE" == close ]] && rm -f "$FAIL_FILE"
  else
    local n last
    n=$(( $(cat "$FAIL_FILE" 2>/dev/null || echo 0) + 1 ))
    echo "$n" >"$FAIL_FILE"
    # 2.º fallo seguido y luego ~1 vez al día (8 latidos/día): sin spam en el brief
    if [[ $n -eq 2 || $((n % 8)) -eq 0 ]]; then
      last="$(git -C "$REPO" log -1 --format=%cd --date=iso origin/main -- subsystem/heartbeat/ 2>/dev/null || echo desconocido)"
      ${HEARTBEAT_STATUS_CMD:-secretary} status 🚫 "" "sec-heartbeat falló $n corridas seguidas (modo $MODE, rc=$rc); último latido en main: $last" \
        --state "latest.md desactualizado" --next "correr sec-heartbeat-state.sh a mano y revisar el error" \
        >/dev/null 2>&1 || true
    fi
  fi
  exit "$rc"
}
trap heartbeat_exit EXIT
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
  git fetch -q origin main
  CLOSE_WT="$(mktemp -d)/main"
  git worktree add -q --detach "$CLOSE_WT" origin/main
  WT_HB="$CLOSE_WT/subsystem/heartbeat"
  mkdir -p "$WT_HB"
  {
    printf '\n## Latido %s (%s)\n\n' "$HHMM" "${SLOT_FILE:-$SLOT}"
    sed '1{/^# Heartbeat/d;}' "$LATEST"
  } >>"$WT_HB/$DAY.md"
  cp "$LATEST" "$WT_HB/latest.md"
  [[ -f "$HB_DIR/state.json" ]] && cp "$HB_DIR/state.json" "$WT_HB/state.json"
  git -C "$CLOSE_WT" add subsystem/heartbeat/
  if ! git -C "$CLOSE_WT" diff --cached --quiet; then
    git -C "$CLOSE_WT" commit -q -m "chore(heartbeat): latido ${SLOT_FILE:-$SLOT} $TS"
  fi
  if ! git -C "$CLOSE_WT" push -q origin HEAD:main; then
    git -C "$CLOSE_WT" fetch -q origin main
    git -C "$CLOSE_WT" rebase origin/main
    git -C "$CLOSE_WT" push -q origin HEAD:main
  fi
  # Checkout local: lo publicado ya vive en origin/main; descarta la copia local de
  # subsystem/heartbeat/ y avanza main si se puede (sin tocar cambios ajenos).
  git fetch -q origin main
  git restore --source=HEAD --staged --worktree -- subsystem/heartbeat/ 2>/dev/null || true
  for f in "$DAY.md" latest.md state.json; do
    git ls-files --error-unmatch "subsystem/heartbeat/$f" >/dev/null 2>&1 || rm -f "$HB_DIR/$f"
  done
  if [[ "$(git symbolic-ref --short -q HEAD)" == main ]]; then
    git merge --ff-only -q origin/main 2>/dev/null \
      || echo "[sec-heartbeat-state] aviso: main local no avanzó (cambios ajenos chocan); queda detrás de origin/main" >&2
  fi
  echo "[sec-heartbeat-state] cerrado: $HB_DIR/$DAY.md + push a main"
  exit 0
fi

# ------------------------------------------------------------------ write / dry-run
if [[ "$MODE" == write ]]; then
  cd "$REPO"
  git fetch -q origin main
  NON_HB="$("$ROUTINES_OPS/main-checkout-guard.sh" "$REPO" 2>/dev/null || true)"
  if [[ -n "$NON_HB" ]]; then
    echo "[sec-heartbeat-state] aviso: el checkout tiene cambios ajenos; no se toca (el cierre va por worktree):" >&2
    printf '%s\n' "$NON_HB" >&2
  fi
  if [[ "$(git symbolic-ref --short -q HEAD)" == main ]]; then
    git restore -- subsystem/heartbeat/ 2>/dev/null || true
    git merge --ff-only -q origin/main 2>/dev/null \
      || echo "[sec-heartbeat-state] aviso: main local no avanzó; se lee un estado atrasado respecto de origin/main" >&2
  else
    echo "[sec-heartbeat-state] aviso: el checkout no está en main; se lee la rama actual" >&2
  fi
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
if ! "$ROUTINES_OPS/extractor-freshness.sh" >"$FRESH_FILE" 2>&1; then
  printf '(extractor-freshness.sh falló)\n%s\n' "$(cat "$FRESH_FILE")" >"$FRESH_FILE.tmp"
  mv "$FRESH_FILE.tmp" "$FRESH_FILE"
fi

PYTHONPATH="$SECRETARY_CORE${PYTHONPATH:+:$PYTHONPATH}" python3 "$ROUTINES_OPS/heartbeat_state.py" \
  --out-dir "$OUT_DIR" --prev-state "$PREV_STATE" --freshness-file "$FRESH_FILE" \
  --slot "$SLOT" --source "$SOURCE"
