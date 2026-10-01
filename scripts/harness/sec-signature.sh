#!/usr/bin/env bash
# sec-signature.sh — firma contextual enriquecida para artefactos GitHub (PR, issue, comentario).
#
# Uso:
#   sec-signature.sh [<contexto>]              # marca + separador + footer
#   sec-signature.sh [<contexto>] --mark
#   sec-signature.sh [<contexto>] --footer
#
# Contexto (prioridad): arg posicional > SECRETARY_SIGNATURE_CONTEXT > SECRETARY_SKILL > sesion
#
# Env opcionales (enriquecen marca y footer cuando están definidos):
#   SECRETARY_RUN_ID, SECRETARY_MODEL | SECRETARY_AGENT_MODEL, SECRETARY_BRANCH,
#   SECRETARY_AGENT_REF, SECRETARY_RUNTIME, SECRETARY_SIGNATURE_DATE
#
# Runtime (autor visible): cursor | claude-code | sesion | api
#   - SECRETARY_RUNTIME fuerza el valor (run-routine.sh exporta cursor|claude|api)
#   - Si no, se infiere del proceso padre (agent → cursor, claude → claude-code)
#
# Contextos especiales:
#   secretary-briefing → autor "Secretary", contexto "briefing" (producto, no runtime genérico)

set -euo pipefail

PART="--both"
if [[ -n "${1:-}" && "$1" == --* ]]; then
  PART="$1"
  CONTEXT="${SECRETARY_SIGNATURE_CONTEXT:-${SECRETARY_SKILL:-sesion}}"
elif [[ -n "${1:-}" ]]; then
  CONTEXT="$1"
  PART="${2:---both}"
else
  CONTEXT="${SECRETARY_SIGNATURE_CONTEXT:-${SECRETARY_SKILL:-sesion}}"
fi

DATE="${SECRETARY_SIGNATURE_DATE:-$(date +%Y-%m-%d)}"
MODEL="${SECRETARY_MODEL:-${SECRETARY_AGENT_MODEL:-}}"
RUN_ID="${SECRETARY_RUN_ID:-}"
REF="${SECRETARY_AGENT_REF:-}"

BRANCH="${SECRETARY_BRANCH:-}"
if [[ -z "$BRANCH" ]]; then
  BRANCH=$(git branch --show-current 2>/dev/null || true)
fi

run_short=""
if [[ -n "$RUN_ID" ]]; then
  run_short="${RUN_ID##*-}"
fi

detect_runtime() {
  if [[ -n "${SECRETARY_RUNTIME:-}" ]]; then
    echo "$SECRETARY_RUNTIME"
    return
  fi
  local p=$$
  local cmd
  for _ in {1..15}; do
    cmd=$(ps -o command= -p "$p" 2>/dev/null || true)
    [[ -z "$cmd" ]] && break
    if [[ "$cmd" == *antigravity* ]] || [[ "$cmd" == *language_server* ]]; then
      echo antigravity
      return
    fi
    if [[ "$cmd" == *cursor-agent* ]] || [[ "$cmd" == *"/agent "* ]] || [[ "$cmd" == *".local/bin/agent"* ]]; then
      echo cursor
      return
    fi
    if [[ "$cmd" == *claude* ]] && [[ "$cmd" != *sec-signature* ]] && [[ "$cmd" != *cursor-agent* ]]; then
      echo claude-code
      return
    fi
    p=$(ps -o ppid= -p "$p" 2>/dev/null | tr -d ' ')
    [[ -z "$p" || "$p" == "0" || "$p" == "1" ]] && break
  done
  echo sesion
}

runtime=$(detect_runtime)
[[ "$runtime" == "claude" ]] && runtime=claude-code

author_label() {
  case "$1" in
    cursor) echo "Cursor" ;;
    api) echo "API cron" ;;
    antigravity) echo "Antigravity" ;;
    claude-code|sesion) echo "Claude Code" ;;
    *) echo "Claude Code" ;;
  esac
}

build_mark() {
  local line="agent-generated:${CONTEXT} runtime=${runtime}"
  [[ -n "$RUN_ID" ]] && line+=" run=${RUN_ID}"
  [[ -n "$BRANCH" ]] && line+=" branch=${BRANCH}"
  [[ -n "$MODEL" ]] && line+=" model=${MODEL}"
  [[ -n "$REF" ]] && line+=" ref=${REF}"
  echo "<!-- ${line} -->"
}

build_footer() {
  local author base
  case "$CONTEXT" in
    secretary-briefing)
      author="Secretary"
      base="🤖 _${author} · briefing"
      ;;
    *)
      author=$(author_label "$runtime")
      base="🤖 _${author} · ${CONTEXT}"
      ;;
  esac
  [[ -n "$BRANCH" ]] && base+=" → ${BRANCH}"
  if [[ -n "$MODEL" && "$MODEL" != "auto" ]]; then
    base+=" · ${MODEL}"
  fi
  [[ -n "$run_short" ]] && base+=" · run ${run_short}"
  base+=" · ${DATE}_"
  echo "$base"
}

MARK=$(build_mark)
FOOTER=$(build_footer)

case "$PART" in
  --mark) echo "$MARK" ;;
  --footer) echo "$FOOTER" ;;
  --both|*)
    printf '%s\n\n---\n%s\n' "$MARK" "$FOOTER"
    ;;
esac
