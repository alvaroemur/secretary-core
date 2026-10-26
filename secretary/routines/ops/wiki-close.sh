#!/usr/bin/env bash
# Cierre de wiki-update sin LLM (D15.8, n5 pieza 3): build, deploy y PR.
#
#   wiki-close.sh --wt <path> --branch <branch> --body-file <file> [--repo <path>] [--dry-run]
#
# 1. Build: SECRETARY_DATA="$WT" python3 wiki/build/build.py. Falla (exit 4, sin
#    deploy ni PR) si el build falla o imprime `Generados 0 artículos`.
# 2. Deploy: wiki/deploy-output.sh. Si falla, se reporta y la corrida sigue.
# 3. PR: routine-pr.sh close con label hilo:wiki. Al body se le suma la línea de
#    build y deploy.
#
# stdout: BUILD_ARTICLES=… DEPLOY=published|identical|failed|dry-run y luego la
#         línea RESULT=… de routine-pr.sh close (exit 3 = push sin PR).
# --dry-run: el build corre sobre una copia temporal del engine (no toca
#            wiki/output); no despliega; routine-pr.sh close corre en --dry-run.
set -euo pipefail

# shellcheck source=../_layout.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/_layout.sh"

die() { echo "wiki-close: $*" >&2; exit 2; }

WT=""; BRANCH=""; BODY_FILE=""; REPO="$SECRETARY_INSTANCE"; DRY=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --wt) WT="$2"; shift 2 ;;
    --branch) BRANCH="$2"; shift 2 ;;
    --body-file) BODY_FILE="$2"; shift 2 ;;
    --repo) REPO="$2"; shift 2 ;;
    --dry-run) DRY=1; shift ;;
    *) die "argumento desconocido: $1" ;;
  esac
done
[[ -n "$WT" && -n "$BRANCH" && -n "$BODY_FILE" ]] || die "requiere --wt, --branch y --body-file"
[[ -d "$WT" ]] || die "no existe el worktree $WT"
[[ -f "$BODY_FILE" ]] || die "no existe el body $BODY_FILE"

WIKI="$SECRETARY_CORE/wiki"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

# 1. Build
BUILD_PY="$WIKI/build/build.py"
if [[ "$DRY" == 1 ]]; then
  mkdir -p "$TMP/engine"
  cp -R "$WIKI/build" "$TMP/engine/build"
  [[ -d "$WIKI/assets" ]] && cp -R "$WIKI/assets" "$TMP/engine/assets"
  BUILD_PY="$TMP/engine/build/build.py"
fi
if ! build_out="$(SECRETARY_DATA="$WT" python3 "$BUILD_PY" 2>&1)"; then
  echo "$build_out" >&2; echo "wiki-close: build falló; no se despliega ni se abre PR" >&2; exit 4
fi
articles="$(sed -nE 's/.*Generados ([0-9]+) artículos.*/\1/p' <<<"$build_out" | tail -1)"
if [[ -z "$articles" || "$articles" == 0 ]]; then
  echo "$build_out" >&2
  echo "wiki-close: el build generó ${articles:-?} artículos; no se despliega ni se abre PR" >&2
  exit 4
fi

# 2. Deploy
if [[ "$DRY" == 1 ]]; then
  deploy="dry-run"; echo "[dry-run] $WIKI/deploy-output.sh sync-wiki $(date +%F)" >&2
elif deploy_out="$("$WIKI/deploy-output.sh" "sync-wiki $(date +%F)" 2>&1)"; then
  if grep -q 'idéntico' <<<"$deploy_out"; then deploy="identical"; else deploy="published"; fi
else
  deploy="failed"; echo "$deploy_out" >&2
fi
echo "BUILD_ARTICLES=$articles DEPLOY=$deploy"

# 3. PR
body="$TMP/body.md"
{
  cat "$BODY_FILE"; echo
  echo "**Build y deploy:** $articles artículos generados; deploy: $deploy."
} >"$body"
args=(close --repo "$REPO" --wt "$WT" --branch "$BRANCH" --body-file "$body"
      --title "chore(wiki): corrida automática $(date +%F)" --routine wiki-update --label hilo:wiki)
[[ "$DRY" == 1 ]] && args+=(--dry-run)
"$ROUTINES_OPS/routine-pr.sh" "${args[@]}"
