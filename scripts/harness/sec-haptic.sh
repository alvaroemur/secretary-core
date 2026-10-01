#!/usr/bin/env bash
# sec-haptic.sh — emisor único de sonido para los haptics de secretary.
# Doctrina: ~/.secretary/_design/doctrinas/sec-haptics.md
#
# Uso:
#   sec-haptic.sh detecto                      # 👀 notice  -> Glass
#   sec-haptic.sh compuerta "texto a decir"    # 🔔 alert   -> Submarine + voz Jimena
#   sec-haptic.sh traba                        # 🔔 alert   -> Sosumi (solo tono)
#   sec-haptic.sh notify                       # hook Notification -> tono de alerta, sin voz
#
# Pensado para correr SIN sandbox (el shell sandboxeado no alcanza los parlantes).
# Cuando lo llama el agente, debe ser con dangerouslyDisableSandbox.
# Escribe una línea de log por invocación para diagnosticar disparo + audio.

set -uo pipefail
SOUNDS=/System/Library/Sounds
LOG="$HOME/.claude/scripts/sec-haptic.log"
SIGNAL="${1:-}"
MSG="${2:-}"

play() { afplay "$1" >/dev/null 2>&1; }

rc=0
case "$SIGNAL" in
  detecto)    play "$SOUNDS/Glass.aiff"; rc=$? ;;
  compuerta)  play "$SOUNDS/Submarine.aiff"; rc=$?
              [ -n "$MSG" ] && say -v Jimena "$MSG" >/dev/null 2>&1 ;;
  traba)      play "$SOUNDS/Sosumi.aiff"; rc=$? ;;
  notify)     play "$SOUNDS/Submarine.aiff"; rc=$? ;;   # hook: alerta mecánica, solo tono
  *)          echo "sec-haptic: señal desconocida '$SIGNAL'" >&2; exit 2 ;;
esac

# Diagnóstico: ¿llegó el disparo (hook vs agente) y corrió el audio (rc=0)?
printf '%s\t%-10s\tafplay_rc=%s\tsrc=%s\n' \
  "$(date '+%Y-%m-%d %H:%M:%S')" "$SIGNAL" "$rc" "${SEC_HAPTIC_SRC:-cli}" >> "$LOG"
exit 0
