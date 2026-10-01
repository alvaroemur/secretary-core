#!/bin/bash
# SessionStart hook: report native Google Drive pointer files under ~/Cowork/.
# Only reports — never rm (deleting pointers sends natives to Drive trash).
# Exit 0 always; do not block session.

COWORK="${HOME}/Cowork"
[ -d "$COWORK" ] || exit 0

FOUND=$(find "$COWORK" \( \
  -name '*.gsheet' -o -name '*.gdoc' -o -name '*.gslides' \
  -o -name '*.gform' -o -name '*.gdraw' -o -name '*.gmap' \
  -o -name '*.gjam' \
\) -print 2>/dev/null)

if [ -n "$FOUND" ]; then
  COUNT=$(printf '%s\n' "$FOUND" | sed '/^$/d' | wc -l | tr -d ' ')
  printf '💡 _secretary detectó — %s puntero(s) nativo(s) de Drive bajo ~/Cowork/_\n' "$COUNT"
  printf "cowork nativos check: punteros nativos de Drive bajo ~/Cowork/\n"
  printf "%s\n" "$FOUND"
  printf "Remediation: mover el nativo en Drive (p. ej. gog drive move); no git add ni rm del puntero local.\n"
  printf "Doctrina: ~/.secretary/rules/drive-cowork.md · spec ~/.secretary/_diseño/specs/L4-drive/004-nativos-drive/spec.md\n"
  if [ -x "$HOME/.claude/scripts/sec-haptic.sh" ]; then
    SEC_HAPTIC_SRC=cowork-nativos-check "$HOME/.claude/scripts/sec-haptic.sh" detecto >/dev/null 2>&1 &
  fi
fi

exit 0
