#!/usr/bin/env python3
"""Inventario de pendientes de wiki-update sin LLM (D15.8, n5 pieza 2).

Junta los ítems `- pendiente_wiki: true` de `<wt>/*/memory/*.md` y
`<wt>/extractors/*/memory/*.md` (fuera de fences) en un JSON compacto: archivo,
línea, header, tipo, campos clave y procedencia.

  wiki-pending.py --wt <worktree> [--prov <tsv>] [--out <json>] [--no-origin] [--dry-run]

Procedencia: `PR#N` si (archivo, header) está en el TSV `$PROV` de W0; si no,
`preexistente` con el commit que introdujo el header (`git log -1 -S`), salvo
`--no-origin`. Solo lee: no integra ni flipea.
--dry-run: no escribe --out; imprime el JSON en stdout.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

FLAG_RE = re.compile(r"^\s*-\s*pendiente_wiki:\s*true\b(.*)$")
HEADER_RE = re.compile(r"^#{2,3} ")
FIELD_RE = re.compile(r"^-\s*([\w_áéíóúñ]+):\s*(.*)$")
KEY_FIELDS = ("tipo", "estado", "responsable", "deadline", "proyecto", "contexto", "slug_existente",
              "detectado", "origen", "fuente", "fuentes")
MAX_VALUE = 160
TYPES = {"acciones": "accion", "personas": "persona", "organizaciones": "organizacion",
         "entidades": "entidad", "reuniones": "reunion", "chats": "chat", "proyectos": "proyecto",
         "suscripciones": "suscripcion", "temas": "tema"}


def memory_files(wt: Path) -> list[Path]:
    files = (set(wt.glob("*/memory/*.md")) | set(wt.glob("extractors/*/memory/*.md"))
             | set(wt.glob("extractors/whatsapp/memory/reviews/*.md")))
    return sorted(f for f in files if f.is_file())


def file_type(path: Path) -> str:
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", path.stem):
        return "memo"
    return TYPES.get(path.stem, path.stem)


def scan(path: Path, rel: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    header, header_line, fields = "", 0, {}
    in_fence = False
    for i, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if HEADER_RE.match(line):
            header, header_line, fields = line.rstrip(), i, {}
            continue
        flag = FLAG_RE.match(line)
        if flag:
            note = flag.group(1).strip().lstrip("#—-").strip()
            item = {"archivo": rel, "linea": header_line or i, "header": header, "tipo": file_type(path),
                    "campos": dict(fields)}
            if note:
                item["nota"] = note[:MAX_VALUE]
            items.append(item)
            continue
        field = FIELD_RE.match(line.strip())
        if field and field.group(1) in KEY_FIELDS:
            fields[field.group(1)] = field.group(2).strip()[:MAX_VALUE]
    return items


def load_prov(path: Path | None) -> dict[tuple[str, str], str]:
    prov: dict[tuple[str, str], str] = {}
    if path is None or not path.exists():
        return prov
    for row in path.read_text(encoding="utf-8").splitlines():
        parts = row.split("\t")
        if len(parts) >= 3:
            prov.setdefault((parts[0], parts[1].rstrip()), parts[2])
    return prov


def origin(wt: Path, rel: str, header: str) -> str:
    if not header:
        return ""
    out = subprocess.run(["git", "-C", str(wt), "log", "-1", "--format=%h %s", "-S", header, "--", rel],
                         capture_output=True, text=True)
    return out.stdout.strip() if out.returncode == 0 else ""


def build(wt: Path, prov_path: Path | None, with_origin: bool) -> dict[str, Any]:
    prov = load_prov(prov_path)
    items: list[dict[str, Any]] = []
    by_file: dict[str, int] = {}
    for path in memory_files(wt):
        rel = path.relative_to(wt).as_posix()
        found = scan(path, rel)
        if found:
            by_file[rel] = len(found)
        items += found
    counts = {"pr": 0, "preexistente": 0}
    for item in items:
        pr = prov.get((item["archivo"], item["header"]))
        if pr:
            item["procedencia"] = pr
            counts["pr"] += 1
        else:
            item["procedencia"] = "preexistente"
            counts["preexistente"] += 1
            if with_origin:
                item["commit_origen"] = origin(wt, item["archivo"], item["header"])
    return {"wt": str(wt), "total": len(items), "por_procedencia": counts, "por_archivo": by_file,
            "items": items}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--wt", required=True, type=Path)
    ap.add_argument("--prov", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--no-origin", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if not args.wt.is_dir():
        print(f"wiki-pending: no existe {args.wt}", file=sys.stderr)
        return 2
    result = build(args.wt.resolve(), args.prov, not args.no_origin)
    text = json.dumps(result, ensure_ascii=False, indent=1) + "\n"
    if args.out and not args.dry_run:
        args.out.write_text(text, encoding="utf-8")
        print(f"wiki-pending: {result['total']} ítems → {args.out}")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
