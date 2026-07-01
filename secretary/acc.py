"""Fold action closure into acciones.md (replaces sec-acc-fold.sh)."""

from __future__ import annotations

import os
import re
from datetime import date
from pathlib import Path

from secretary.config import resolve_path_key


def fold_action(
    acc_id: str,
    evidencia: str,
    cerrado: str | None = None,
    estado: str | None = None,
) -> str:
    cerrado = cerrado or date.today().isoformat()
    estado = estado or os.environ.get("SEC_ACC_ESTADO", "hecha")

    path = resolve_path_key("meetings.memory") / "acciones.md"
    if not path.is_file():
        raise FileNotFoundError(f"No existe {path}")

    text = path.read_text(encoding="utf-8")
    header = f"## {acc_id}\n"
    idx = text.find(header)
    if idx == -1:
        raise LookupError(f"No encontré entrada canónica {acc_id}")

    if "[update]" in text[idx : idx + len(header) + 10]:
        raise ValueError(f"{acc_id} no es entrada canónica")

    next_hdr = text.find("\n## ", idx + len(header))
    block = text[idx : next_hdr if next_hdr != -1 else len(text)]

    def set_field(b: str, key: str, value: str) -> str:
        pat = re.compile(rf"^- {re.escape(key)}:.*$", re.M)
        repl = f"- {key}: {value}"
        if pat.search(b):
            return pat.sub(repl, b, count=1)
        return b.rstrip() + f"\n{repl}\n"

    block = set_field(block, "estado", estado)
    block = set_field(block, "cerrado", cerrado)
    block = set_field(block, "evidencia_cierre", evidencia)

    new_text = text[:idx] + block + text[next_hdr if next_hdr != -1 else len(text) :]

    fold = f"""
---

## {acc_id} [update]
- estado_nuevo: {estado}
- evidencia: Fold canónico vía secretary acc fold ({evidencia}).
- evidencia_cierre: {evidencia}
- cerrado: {cerrado}
- origen: interactive:secretary-acc-fold
- detectado: {cerrado}
"""

    path.write_text(new_text.rstrip() + fold, encoding="utf-8")
    return f"✓ {acc_id} → {estado} · {evidencia} · cerrado {cerrado}"
