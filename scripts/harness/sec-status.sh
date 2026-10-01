#!/usr/bin/env bash
# sec-status.sh — persiste un avance de tarea como comentario en el brief diario.
# El brief (GitHub Issue) es la superficie de captura: fresco, con timestamp, sin
# problema de rama (gh pega al remoto vivo). pulse lee estos comentarios; el
# briefing los consolida en su carry-over (el ledger durable).
#
# Uso:
#   sec-status.sh "✅" "#1"        "UTEC — evaluaciones enviadas"
#   sec-status.sh "🔄" "acc-...-3" "LinkedIn — bajado el full, falta el fast file"
#   sec-status.sh "⏳" "#3"        "mentoría: aún sin agendar (deadline hoy)"
#
# emoji: ✅ hecho · 🔄 en curso · ⏳ pendiente/bloqueado · 🚫 cancelado
# ref:   número de ítem del brief (#N) o acc-id; texto libre si no hay ref.

set -uo pipefail

if command -v secretary &>/dev/null; then
  exec secretary status "$@"
fi

REPO=alvaroemur/cowork-secretary
EMOJI="${1:?falta emoji de estado}"
REF="${2:-}"
NOTE="${3:?falta la nota}"
NOW=$(date '+%Y-%m-%d %H:%M')

# Brief abierto más reciente (informe-diario). Si no hay, no inventa: avisa y sale.
ISSUE=$(gh issue list --repo "$REPO" --label "tipo:informe-diario" --state open \
  --json number,createdAt --jq 'sort_by(.createdAt) | last | .number' 2>/dev/null)
if [ -z "$ISSUE" ] || [ "$ISSUE" = "null" ]; then
  echo "sec-status: no hay brief abierto (informe-diario) — no se persistió '$NOTE'" >&2
  exit 1
fi

gh issue comment "$ISSUE" --repo "$REPO" --body "$(~/.claude/scripts/sec-signature.sh sec-status --mark)
sec-status · ${NOW} · ${EMOJI} ${REF} — ${NOTE}" >/dev/null

# Señal háptica: actuó (ambient, mudo) — deja rastro de que secretary persistió algo.
[ -x "$HOME/.claude/scripts/sec-haptic.sh" ] && SEC_HAPTIC_SRC=sec-status "$HOME/.claude/scripts/sec-haptic.sh" detecto >/dev/null 2>&1 &

echo "✓ persistido en brief #${ISSUE}: ${EMOJI} ${REF} — ${NOTE}"
