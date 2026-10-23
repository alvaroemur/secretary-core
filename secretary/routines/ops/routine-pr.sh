#!/usr/bin/env bash
# Preludio y cierre comunes de las rutinas que entregan un PR (D15.8, pieza 6).
#
# open  — crea el worktree de la corrida desde origin/main, o desde el PR abierto
#         de una corrida previa cuando la rutina encadena.
#   routine-pr.sh open --scope <scope> [--repo <path>] [--chain-label <label>]
#                      [--chain-pattern <regex>] [--dry-run]
#   stdout (para eval): WT=… BRANCH=… BASE=… PREV_PR=…
#
# close — commit, push, PR firmado con label, cierre del PR superado y limpieza.
#         Sin cambios: solo limpia el worktree y la rama.
#   routine-pr.sh close --wt <path> --branch <branch> --title <title> --body-file <file>
#                       --routine <id> [--repo <path>] [--label <label>]
#                       [--supersede <n>] [--add <path>]... [--dry-run]
#   stdout: RESULT=no-changes | RESULT=pr PR_NUMBER=… PR_URL=… | RESULT=push-only
#   exit 3 = rama empujada pero el PR falló (no se revierte nada).
#
# El worktree vive en ${ROUTINE_WT_ROOT:-/tmp}, no en $TMPDIR: el sistema puede
# limpiar $TMPDIR mientras corren subagentes largos.
set -euo pipefail

# shellcheck source=../_layout.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/_layout.sh"

die() { echo "routine-pr: $*" >&2; exit 2; }
q() { printf '%q' "$1"; }

cmd="${1:-}"; shift || true
REPO="$SECRETARY_INSTANCE"; DRY=0
SCOPE=""; CHAIN_LABEL=""; CHAIN_PATTERN=""
WT=""; BRANCH=""; TITLE=""; BODY_FILE=""; ROUTINE=""; LABEL=""; SUPERSEDE=""; ADD=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo) REPO="$2"; shift 2 ;;
    --scope) SCOPE="$2"; shift 2 ;;
    --chain-label) CHAIN_LABEL="$2"; shift 2 ;;
    --chain-pattern) CHAIN_PATTERN="$2"; shift 2 ;;
    --wt) WT="$2"; shift 2 ;;
    --branch) BRANCH="$2"; shift 2 ;;
    --title) TITLE="$2"; shift 2 ;;
    --body-file) BODY_FILE="$2"; shift 2 ;;
    --routine) ROUTINE="$2"; shift 2 ;;
    --label) LABEL="$2"; shift 2 ;;
    --supersede) SUPERSEDE="$2"; shift 2 ;;
    --add) ADD+=("$2"); shift 2 ;;
    --dry-run) DRY=1; shift ;;
    *) die "argumento desconocido: $1" ;;
  esac
done

run() {
  if [[ "$DRY" == 1 ]]; then echo "[dry-run] $*" >&2; else "$@"; fi
}

open_run() {
  [[ -n "$SCOPE" ]] || die "open requiere --scope"
  cd "$REPO"
  run git worktree prune
  run git fetch -q origin main
  local ts base="origin/main" prev=""
  ts="$(date +%Y%m%d-%H%M)"
  BRANCH="$SCOPE/auto-$ts"
  WT="${ROUTINE_WT_ROOT:-/tmp}/secretary-$SCOPE-$ts"
  if [[ -n "$CHAIN_PATTERN" ]]; then
    local args=(pr list --state open --json number,headRefName,createdAt)
    [[ -n "$CHAIN_LABEL" ]] && args+=(--label "$CHAIN_LABEL")
    local found
    found="$(gh "${args[@]}" --jq "map(select(.headRefName|test(\"$CHAIN_PATTERN\"))) | sort_by(.createdAt) | last | select(. != null) | ((.number|tostring)+\" \"+.headRefName)" 2>/dev/null || true)"
    if [[ -n "$found" && "$found" == *" "* ]]; then
      prev="${found%% *}"
      local prev_branch="${found#* }"
      run git fetch -q origin "$prev_branch"
      base="origin/$prev_branch"
    fi
  fi
  run git worktree add -q -b "$BRANCH" "$WT" "$base"
  echo "WT=$(q "$WT") BRANCH=$(q "$BRANCH") BASE=$(q "$base") PREV_PR=$(q "$prev")"
}

signature() {
  local helper="${SECRETARY_SIGNATURE:-$HOME/.claude/scripts/sec-signature.sh}"
  if [[ -x "$helper" ]]; then "$helper" "$ROUTINE" "$1" 2>/dev/null || true
  else echo "routine-pr: sin helper de firma ($helper)" >&2; fi
}

cleanup() {
  cd "$REPO"
  run git worktree remove --force "$WT" 2>/dev/null || true
  run git branch -D "$BRANCH" >/dev/null 2>&1 || true
}

close_run() {
  [[ -n "$WT" && -n "$BRANCH" && -n "$TITLE" && -n "$BODY_FILE" && -n "$ROUTINE" ]] \
    || die "close requiere --wt, --branch, --title, --body-file y --routine"
  [[ -d "$WT" ]] || die "no existe el worktree $WT"
  [[ -f "$BODY_FILE" ]] || die "no existe el body $BODY_FILE"
  cd "$WT"
  if [[ ${#ADD[@]} -gt 0 ]]; then run git add -- "${ADD[@]}"; else run git add -A; fi
  # Cambios = algo en stage (en dry-run, algo en el árbol) o commits locales que
  # ningún remoto tiene. Encadenar sobre un PR previo sin cambios nuevos no cuenta.
  local pending unpushed
  if [[ "$DRY" == 1 ]]; then pending="$(git status --porcelain)"; else pending="$(git diff --cached --name-only)"; fi
  unpushed="$(git rev-list --count HEAD --not --remotes)"
  if [[ -z "$pending" && "$unpushed" == 0 ]]; then
    cleanup; echo "RESULT=no-changes"; return 0
  fi
  if [[ -n "$pending" ]]; then run git commit -q -m "$TITLE"; fi
  run git push -q -u origin "$BRANCH"
  local body; body="$(mktemp)"
  { signature --mark; echo; cat "$BODY_FILE"; echo; echo "---"; signature --footer; } >"$body"
  if [[ -n "$LABEL" ]]; then
    run gh label create "$LABEL" --color 0E8A16 >/dev/null 2>&1 || true
  fi
  local pr_args=(pr create --base main --head "$BRANCH" --title "$TITLE" --body-file "$body")
  [[ -n "$LABEL" ]] && pr_args+=(--label "$LABEL")
  local url=""
  if [[ "$DRY" == 1 ]]; then
    echo "[dry-run] gh ${pr_args[*]}" >&2; url="dry-run"
  elif ! url="$(gh "${pr_args[@]}")"; then
    rm -f "$body"; echo "RESULT=push-only"; exit 3
  fi
  rm -f "$body"
  local num="${url##*/}"
  if [[ -n "$SUPERSEDE" && "$SUPERSEDE" != "$num" ]]; then
    run gh pr close "$SUPERSEDE" --delete-branch --comment "Superado por #$num (lo continúa e incluye su contenido)." || true
  fi
  cd "$REPO"; run git worktree remove --force "$WT" 2>/dev/null || true
  echo "RESULT=pr PR_NUMBER=$(q "$num") PR_URL=$(q "$url")"
}

case "$cmd" in
  open) open_run ;;
  close) close_run ;;
  *) die "uso: routine-pr.sh open|close …" ;;
esac
