#!/usr/bin/env bash
# inject-heartbeat-freshness.sh — inserta o reemplaza ## Frescura extractoras en latest.md.
# Uso: inject-heartbeat-freshness.sh [path/to/latest.md]
set -euo pipefail

# shellcheck source=../_layout.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/_layout.sh"

REPO="${SECRETARY_INSTANCE:-$HOME/.secretary}"
TARGET="${1:-$REPO/subsystem/heartbeat/latest.md}"
FRESHNESS_SCRIPT="$ROUTINES_OPS/extractor-freshness.sh"

[[ -f "$TARGET" ]] || { echo "inject-heartbeat-freshness: no existe $TARGET" >&2; exit 1; }
[[ -x "$FRESHNESS_SCRIPT" ]] || { echo "inject-heartbeat-freshness: falta $FRESHNESS_SCRIPT" >&2; exit 1; }

export HEARTBEAT_INJECT_TARGET="$TARGET"
export HEARTBEAT_FRESHNESS="$("$FRESHNESS_SCRIPT")"

python3 <<'PY'
import os
import re

path = os.environ["HEARTBEAT_INJECT_TARGET"]
freshness = os.environ["HEARTBEAT_FRESHNESS"].rstrip() + "\n\n"

with open(path, encoding="utf-8") as f:
    content = f.read()

section_re = re.compile(
    r"^## Frescura extractoras\b.*?(?=^## |\Z)",
    re.MULTILINE | re.DOTALL,
)

if section_re.search(content):
    content = section_re.sub(freshness, content, count=1)
else:
    orphans_re = re.compile(
        r"^## Huérfanos\b.*?(?=^## |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    m = orphans_re.search(content)
    if m:
        pos = m.end()
        content = content[:pos] + "\n" + freshness + content[pos:]
    elif "## Pendiente humano" in content:
        content = content.replace("## Pendiente humano", freshness + "## Pendiente humano", 1)
    else:
        content = content.rstrip() + "\n\n" + freshness

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
PY

echo "inject-heartbeat-freshness: actualizado $TARGET"
