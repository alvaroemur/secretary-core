#!/usr/bin/env bash
# Pre-flight for reuniones-update: skip LLM when TACTIQ_ROOT has no new docs.
# Exit 0 = nothing new (caller should skip agent).
# Exit 2 = proceed to full routine (gog/auth/parse issues or new docs found).
set -euo pipefail

# shellcheck source=../_layout.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/_layout.sh"

INSTANCE="${SECRETARY_INSTANCE:-$HOME/.secretary}"
MEETINGS_MEMORY="$INSTANCE/extractors/meetings/memory"
LAYOUT="$MEETINGS_MEMORY/_drive_layout.json"
PROCESADOS="$MEETINGS_MEMORY/_procesados.jsonl"

if [[ ! -f "$LAYOUT" ]]; then
  echo "[reuniones-scout] missing _drive_layout.json — proceeding to agent"
  exit 2
fi

TACTIQ_ROOT="$(jq -r '.tactiq_root_id // empty' "$LAYOUT")"
if [[ -z "$TACTIQ_ROOT" ]]; then
  echo "[reuniones-scout] tactiq_root_id missing — proceeding to agent"
  exit 2
fi

PERSONAL_ACCOUNT=""
if command -v secretary >/dev/null 2>&1; then
  PERSONAL_ACCOUNT="$(secretary config show 2>/dev/null | jq -r '.accounts.personal // empty' || true)"
fi
ACCOUNT_ARGS=()
if [[ -n "$PERSONAL_ACCOUNT" ]]; then
  ACCOUNT_ARGS=(--account="$PERSONAL_ACCOUNT")
fi

if ! command -v gog >/dev/null 2>&1; then
  echo "[reuniones-scout] gog not found — proceeding to agent"
  exit 2
fi

set +e
DRIVE_JSON="$(gog drive ls --parent="$TACTIQ_ROOT" "${ACCOUNT_ARGS[@]}" --json 2>&1)"
GOG_EXIT=$?
set -e

if [[ $GOG_EXIT -ne 0 ]]; then
  echo "[reuniones-scout] gog drive ls failed (exit $GOG_EXIT) — proceeding to agent"
  echo "$DRIVE_JSON"
  exit 2
fi

export REUNIONES_SCOUT_INSTANCE="$INSTANCE"
export REUNIONES_SCOUT_PROCESADOS="$PROCESADOS"
export REUNIONES_SCOUT_DRIVE_JSON="$DRIVE_JSON"
SCOUT_RESULT="$(python3 - <<'PY'
import json
import os
import sys
from pathlib import Path

instance = Path(os.environ["REUNIONES_SCOUT_INSTANCE"])
procesados_path = Path(os.environ["REUNIONES_SCOUT_PROCESADOS"])
drive_json = os.environ.get("REUNIONES_SCOUT_DRIVE_JSON", "")

processed: set[str] = set()
if procesados_path.is_file():
    for line in procesados_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        did = obj.get("drive_id")
        if did:
            processed.add(str(did))

try:
    entries = json.loads(drive_json)
except json.JSONDecodeError:
    print("PARSE_ERROR")
    sys.exit(3)

if isinstance(entries, dict):
    entries = entries.get("files") or entries.get("items") or []

skip_names = {"procesadas", "descartadas"}
new_ids: list[str] = []
for item in entries:
    if not isinstance(item, dict):
        continue
    name = (item.get("name") or "").rstrip("/")
    mime = item.get("mimeType") or ""
    fid = item.get("id") or ""
    if mime == "application/vnd.google-apps.folder" or name in skip_names:
        continue
    if not fid:
        continue
    if str(fid) not in processed:
        new_ids.append(str(fid))

print(f"NEW_COUNT={len(new_ids)}")
for fid in new_ids[:10]:
    print(f"NEW_ID={fid}")
PY
)"

if [[ "$SCOUT_RESULT" == PARSE_ERROR* ]]; then
  echo "[reuniones-scout] could not parse gog JSON — proceeding to agent"
  exit 2
fi

NEW_COUNT="$(printf '%s\n' "$SCOUT_RESULT" | sed -n 's/^NEW_COUNT=//p' | head -1)"
NEW_COUNT="${NEW_COUNT:-0}"

if [[ "$NEW_COUNT" -eq 0 ]]; then
  echo "[reuniones-scout] TACTIQ_ROOT=$TACTIQ_ROOT — 0 new docs (processed ledger has all current files)"
  echo "[reuniones-scout] skipping agent — no LLM spend"
  exit 0
fi

echo "[reuniones-scout] TACTIQ_ROOT=$TACTIQ_ROOT — $NEW_COUNT new doc(s); proceeding to agent"
printf '%s\n' "$SCOUT_RESULT" | grep '^NEW_ID=' | sed 's/^NEW_ID=/  - /'
exit 2
