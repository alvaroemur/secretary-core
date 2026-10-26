#!/usr/bin/env python3
"""Clasifica los compromisos abiertos del owner para la Fase 3.5 de housekeeping.

Solo lee: imprime JSON con lo que se aplica (vía `secretary acc fold`) y lo que se propone.
Reglas: A-reglas, CMP-3 (plan dream-utilidad). Sin ventana de `detectado`: entra todo el ledger.

Uso:
  compromisos.py --ledger <acciones.md> --summaries <dir> [--hoy YYYY-MM-DD] [--terminados a,b]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from secretary.acc import parse_ledger  # noqa: E402

OPEN = {"abierta", "en-curso", "pendiente"}
OWNER = {"mía", "compartida"}
VENCIDA_DIAS = 30
QUIETA_DIAS = 30
REUNION_DIAS = 14
PROPONER_DIAS = 14

_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _fecha(s: str | None) -> date | None:
    m = _DATE.search(s or "")
    try:
        return date.fromisoformat(m.group(0)) if m else None
    except ValueError:
        return None


def proyectos_con_reunion(blocks, summaries: Path, hoy: date) -> dict[str, str]:
    """Proyecto → fecha de su reunión más reciente dentro de REUNION_DIAS.

    Señal: algún compromiso del proyecto nació de un resumen reciente (`origen`). El campo
    `organizaciones` del resumen suele venir vacío y los nombres de archivo mezclan personas.
    """
    desde = hoy - timedelta(days=REUNION_DIAS)
    recientes: dict[str, date] = {}
    for f in summaries.glob("*.md") if summaries.is_dir() else []:
        d = _fecha(f.name)
        if d and desde <= d <= hoy:
            recientes[f.stem] = d
    out: dict[str, date] = {}
    for b in blocks:
        p = b.fields.get("proyecto", "").strip()
        d = recientes.get(Path(b.fields.get("origen", "")).stem)
        if p and d and not b.is_update and (p not in out or d > out[p]):
            out[p] = d
    return {p: d.isoformat() for p, d in out.items()}


def clasificar(text: str, summaries: Path, hoy: date, terminados: set[str]) -> dict:
    _, blocks = parse_ledger(text)
    blocks = [b for b in blocks if not b.irregular]
    canon, estado, movido = {}, {}, {}
    for b in blocks:
        if not b.is_update:
            canon[b.acc_id] = b
            estado[b.acc_id] = b.estado
            movido[b.acc_id] = _fecha(b.fields.get("detectado"))
            continue
        if b.estado:
            estado[b.acc_id] = b.estado
        d = _fecha(b.fields.get("detectado")) or _fecha(b.fields.get("cerrado"))
        if d and (movido.get(b.acc_id) is None or d > movido[b.acc_id]):
            movido[b.acc_id] = d

    reunion = proyectos_con_reunion(blocks, summaries, hoy)
    aplicar, proponer = [], []
    for acc, b in canon.items():
        if estado.get(acc) not in OPEN or b.fields.get("dueño", "").split(" ")[0] not in OWNER:
            continue
        proyecto = b.fields.get("proyecto", "").strip()
        deadline = _fecha(b.fields.get("deadline"))
        detectado = _fecha(b.fields.get("detectado"))
        mov = movido.get(acc)
        vencida = (hoy - deadline).days if deadline else None
        quieta = (hoy - mov).days if mov else None
        fila = {
            "acc": acc,
            "titulo": b.fields.get("titulo", ""),
            "proyecto": proyecto,
            "deadline": deadline.isoformat() if deadline else None,
            "vencida_dias": vencida,
            "quieta_dias": quieta,
        }
        if proyecto in terminados:
            aplicar.append(fila | {"estado": "cancelada", "evidencia": "manual:housekeeping-proyecto-terminado"})
            continue
        if deadline and detectado and deadline < detectado:
            regla = "nacio-muerta"
        elif b.fields.get("tipo", "").startswith("idea") and vencida is not None and vencida > VENCIDA_DIAS:
            regla = "idea-stale"
        elif vencida is not None and vencida > VENCIDA_DIAS and (quieta is None or quieta > QUIETA_DIAS):
            regla = "caducidad-30d"
        else:
            regla = None
        if regla and proyecto in reunion:
            # CMP-3: un proyecto con reunión reciente no caduca solo; va al resumen semanal.
            proponer.append(fila | {"propuesta": "caducada", "regla": regla,
                                    "motivo": f"proyecto con reunión el {reunion[proyecto]}"})
        elif regla:
            aplicar.append(fila | {"estado": "caducada", "evidencia": f"manual:housekeeping-{regla}"})
        elif vencida is not None and vencida > PROPONER_DIAS:
            proponer.append(fila | {"propuesta": "caducada", "regla": "vencida-14d",
                                    "motivo": f"vencida hace {vencida} días"})

    return {
        "hoy": hoy.isoformat(),
        "proyectos_con_reunion": reunion,
        "aplicar": sorted(aplicar, key=lambda r: r["acc"]),
        "proponer": sorted(proponer, key=lambda r: r["acc"]),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ledger", type=Path, required=True)
    ap.add_argument("--summaries", type=Path, required=True)
    ap.add_argument("--hoy", type=date.fromisoformat, default=date.today())
    ap.add_argument("--terminados", default="", help="slugs de proyecto separados por coma")
    a = ap.parse_args(argv)
    terminados = {t.strip() for t in a.terminados.split(",") if t.strip()}
    out = clasificar(a.ledger.read_text(encoding="utf-8"), a.summaries, a.hoy, terminados)
    json.dump(out, sys.stdout, ensure_ascii=False, indent=1)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
