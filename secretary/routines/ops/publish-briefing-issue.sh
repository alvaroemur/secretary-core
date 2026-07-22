#!/usr/bin/env bash
# Publica briefing del día y cierra el issue abierto anterior.
# Uso: publish-briefing-issue.sh <body-file> [YYYY-MM-DD] [DayName]
set -euo pipefail

# shellcheck source=../_layout.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/_layout.sh"

BODY_FILE="${1:?usage: publish-briefing-issue.sh <body-file> [date] [dow]}"
TODAY="${2:-$(date '+%Y-%m-%d')}"
DOW="${3:-$(date '+%A')}"
REPO="${SECRETARY_REPO:-yourusername/cowork-secretary}"

MARK=$(~/.claude/scripts/sec-signature.sh secretary-briefing --mark)
FOOT=$(~/.claude/scripts/sec-signature.sh secretary-briefing --footer)
# BSD head (macOS) no soporta head -n -1
TAIL=$(tail -n +2 "$BODY_FILE" | sed '$d')
BODY=$(printf '%s\n%s\n\n%s' "$MARK" "$TAIL" "$FOOT")

NEW=$(gh issue create \
  --repo "$REPO" \
  --title "📋 Briefing — $TODAY ($DOW)" \
  --label "tipo:informe-diario" \
  --assignee "${BRIEF_ASSIGNEE:-yourusername}" \
  --body "$BODY")

NEW_NUM=$(echo "$NEW" | grep -oE '[0-9]+$')
echo "Created: $NEW"

PREV=$(gh issue list --repo "$REPO" --label "tipo:informe-diario" --state open \
  --json number,createdAt \
  --jq "sort_by(.createdAt) | reverse | map(.number) | map(select(. != $NEW_NUM)) | .[0]")

if [[ -n "$PREV" && "$PREV" != "null" ]]; then
  gh issue comment "$PREV" --repo "$REPO" --body "$(~/.claude/scripts/sec-signature.sh secretary-briefing --mark)
Cerrando este briefing. Lo abierto se trasladó a #$NEW_NUM.

---
$(~/.claude/scripts/sec-signature.sh secretary-briefing --footer)"
  gh issue close "$PREV" --repo "$REPO"
  echo "Closed previous: #$PREV"
fi

echo "Done: https://github.com/$REPO/issues/$NEW_NUM"
