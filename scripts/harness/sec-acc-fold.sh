#!/usr/bin/env bash
# sec-acc-fold.sh — pliega cierre de acción en la entrada canónica de acciones.md (spec 007).
# Usar tras merge de PR vinculado, sec-status, o reconciliación manual.
#
# Uso:
#   sec-acc-fold.sh acc-20260622-001 pr:alvaroemur/planv-alma#2
#   sec-acc-fold.sh acc-20260622-001 pr:alvaroemur/planv-alma#2 2026-06-25
#
# estado_nuevo: hecha (default) | en-curso | cancelada | caducada

set -euo pipefail

if command -v secretary &>/dev/null; then
  if [ -n "${3:-}" ]; then
    exec secretary acc fold "$1" "$2" "$3"
  else
    exec secretary acc fold "$1" "$2"
  fi
fi

ACC_ID="${1:?falta acc-id}"
EVIDENCIA="${2:?falta evidencia_cierre (ej. pr:owner/repo#N)}"
CERRADO="${3:-$(date '+%Y-%m-%d')}"
ESTADO="${SEC_ACC_ESTADO:-hecha}"
INSTANCE="${SECRETARY_INSTANCE:-$HOME/.secretary}"
ACCIONES="$INSTANCE/extractors/meetings/memory/acciones.md"

if [ ! -f "$ACCIONES" ]; then
  echo "sec-acc-fold: no existe $ACCIONES" >&2
  exit 1
fi

export ACC_ID EVIDENCIA CERRADO ESTADO ACCIONES
python3 <<'PY'
import os, re, sys
from pathlib import Path

acc_id = os.environ["ACC_ID"]
evidencia = os.environ["EVIDENCIA"]
cerrado = os.environ["CERRADO"]
estado = os.environ["ESTADO"]
path = Path(os.environ["ACCIONES"])
text = path.read_text()
header = f"## {acc_id}\n"
idx = text.find(header)
if idx == -1:
    print(f"sec-acc-fold: no encontré entrada canónica {acc_id}", file=sys.stderr)
    sys.exit(1)
# Solo entrada canónica (sin [update])
if text[idx:idx+len(header)+10].find("[update]") != -1:
    print(f"sec-acc-fold: {acc_id} no es entrada canónica", file=sys.stderr)
    sys.exit(1)

next_hdr = text.find("\n## ", idx + len(header))
block = text[idx:next_hdr if next_hdr != -1 else len(text)]

def set_field(b: str, key: str, value: str) -> str:
    pat = re.compile(rf"^- {re.escape(key)}:.*$", re.M)
    repl = f"- {key}: {value}"
    if pat.search(b):
        return pat.sub(repl, b, count=1)
    return b.rstrip() + f"\n{repl}\n"

block = set_field(block, "estado", estado)
block = set_field(block, "cerrado", cerrado)
block = set_field(block, "evidencia_cierre", evidencia)

new_text = text[:idx] + block + text[next_hdr if next_hdr != -1 else len(text):]

fold = f"""
---

## {acc_id} [update]
- estado_nuevo: {estado}
- evidencia: Fold canónico vía sec-acc-fold ({evidencia}).
- evidencia_cierre: {evidencia}
- cerrado: {cerrado}
- origen: interactive:sec-acc-fold
- detectado: {cerrado}
"""

path.write_text(new_text.rstrip() + fold)
print(f"✓ {acc_id} → {estado} · {evidencia} · cerrado {cerrado}")
PY
