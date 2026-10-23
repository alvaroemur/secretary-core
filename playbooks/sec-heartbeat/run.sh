#!/usr/bin/env bash
# sec-heartbeat — main-only orchestrator (no worktree, no PR).
set -euo pipefail

REPO="${SECRETARY_INSTANCE:-$HOME/.secretary}"
CORE="${SECRETARY_CORE:-$HOME/Dev/secretary-core}"
PLAYBOOK="$HOME/.claude/scheduled-tasks/sec-heartbeat/SKILL.md"
ENTRY="$REPO/.cursor/routines/sec-heartbeat.md"
DRY_RUN="${DRY_RUN:-0}"

export SECRETARY_RUNTIME=cursor
export SECRETARY_INSTANCE="$REPO"
export SECRETARY_CORE="$CORE"
export TZ="${TZ:-America/Lima}"

# Rutinas programadas usan Auto (cuota ilimitada); override: SECRETARY_AGENT_MODEL
AGENT_MODEL="${SECRETARY_AGENT_MODEL:-auto}"

detect_slot() {
  local hour minute
  hour=$(date +%H | sed 's/^0//')
  minute=$(date +%M | sed 's/^0//')
  hour=${hour:-0}
  minute=${minute:-0}

  if [[ "$hour" -eq 7 && "$minute" -ge 5 && "$minute" -le 15 ]]; then
    echo "pre-brief"
  elif [[ "$hour" -eq 0 && "$minute" -ge 5 && "$minute" -le 15 ]]; then
    echo "close"
  else
    echo "q2h"
  fi
}

SLOT="${HEARTBEAT_SLOT:-$(detect_slot)}"
TIMESTAMP="$(date '+%Y-%m-%d %H:%M')"

echo "[sec-heartbeat] slot=$SLOT timestamp=$TIMESTAMP repo=$REPO"

cd "$REPO"
git fetch origin main
git checkout main

# Allow dirty subsystem/heartbeat/ (will be overwritten); abort on other dirty paths
DIRTY="$(git status --porcelain)"
# Solo tracked dirty bloquea; untracked (??) es ruido de sesiones/worktrees — no abortar.
NON_HB="$(printf '%s\n' "$DIRTY" | grep -v '^??' | grep -v ' subsystem/heartbeat/' | grep -v '^$' || true)"
if [[ -n "$NON_HB" ]]; then
  echo "[sec-heartbeat] abort: checkout has non-heartbeat dirty files:" >&2
  printf '%s\n' "$NON_HB" >&2
  exit 1
fi
if printf '%s\n' "$DIRTY" | grep -q ' subsystem/heartbeat/'; then
  git restore subsystem/heartbeat/ 2>/dev/null || git checkout -- subsystem/heartbeat/
fi

git pull --rebase origin main

if [[ "$DRY_RUN" == "1" ]]; then
  echo "[sec-heartbeat] DRY_RUN=1 — skipping agent, commit and push"
  exit 0
fi

FRESHNESS_SCRIPT="$REPO/scripts/routines/extractor-freshness.sh"
EXTRACTOR_FRESHNESS=""
if [[ -x "$FRESHNESS_SCRIPT" ]]; then
  EXTRACTOR_FRESHNESS="$("$FRESHNESS_SCRIPT" 2>&1)" || EXTRACTOR_FRESHNESS="(extractor-freshness.sh falló: $?)"
else
  EXTRACTOR_FRESHNESS="(extractor-freshness.sh no encontrado)"
fi

if [[ ! -f "$ENTRY" ]]; then
  echo "Missing entry point: $ENTRY" >&2
  exit 1
fi

PROMPT="$(cat <<EOF
Ejecuta la rutina sec-heartbeat completa.

Slot: $SLOT
Timestamp: $TIMESTAMP (America/Lima)
Playbook: $PLAYBOOK

Reglas duras:
- Escribe SOLO en subsystem/heartbeat/ (latest.md + YYYY-MM-DD.md append).
- Checkout main en $REPO — NO worktree, NO PR.
- Incluye en latest.md la sección ## Frescura extractoras **verbatim** (bloque precomputado abajo).
- Al terminar: git add subsystem/heartbeat/ && commit && push origin main.
- Mensaje de commit: chore(heartbeat): latido $SLOT $TIMESTAMP

## Frescura extractoras (precomputada — copiar verbatim)

$EXTRACTOR_FRESHNESS

$(cat "$ENTRY")
EOF
)"

INVOKE="$REPO/scripts/routines/invoke-agent.sh"
chmod +x "$INVOKE" "$REPO/scripts/routines/routine-stream-tee.py" "$REPO/scripts/routines/parse-routine-metrics.py" 2>/dev/null || true
"$INVOKE" sec-heartbeat "$REPO" "$PROMPT"

INJECT_SCRIPT="$REPO/scripts/routines/inject-heartbeat-freshness.sh"
if [[ -x "$INJECT_SCRIPT" && -f "$REPO/subsystem/heartbeat/latest.md" ]]; then
  "$INJECT_SCRIPT" "$REPO/subsystem/heartbeat/latest.md" || true
fi

# Safety net: commit/push if agent wrote but did not persist
if git status --porcelain subsystem/heartbeat/ | grep -q .; then
  git add subsystem/heartbeat/
  git commit -m "chore(heartbeat): latido $SLOT $TIMESTAMP"
fi

if git status -sb | grep -q 'ahead'; then
  git push origin main
fi

echo "[sec-heartbeat] done slot=$SLOT"
