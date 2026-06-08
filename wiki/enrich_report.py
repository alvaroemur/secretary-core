#!/usr/bin/env python3
"""Reporte read-only de enriquecimiento del grafo de wikilinks.

PROTOTIPO. No toca el pipeline ni los artículos: solo lee `articulos/**/*.md`,
parsea los wikilinks `[[categoria/slug|label]]` y reporta:
  - backlinks (in-degree) por nodo: quién es citado por más artículos
  - co-ocurrencia: pares de entidades citadas juntas por muchos terceros

La detección de referencias rotas/orphans NO vive aquí: es trabajo de
`scripts/ci/validate_wikilinks.py` (que sabe distinguir grandfathered /
pendiente_wiki / tolerada). Duplicarla reintroduciría ruido ya resuelto.

Resuelve la ruta de la instancia vía SECRETARY_INSTANCE (default ~/.secretary),
sin __file__. Excluye `_index` y `alvaro-mur` del cómputo de co-ocurrencia
(hubs que distorsionan: Álvaro aparece en casi todo artículo).
"""
import os
import re
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

INSTANCE = Path(os.environ.get("SECRETARY_INSTANCE", str(Path.home() / ".secretary")))
ARTICULOS = INSTANCE / "wiki" / "articulos"

WIKILINK = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]")
# hubs excluidos del cómputo de co-ocurrencia (distorsionan el ranking)
EXCLUDE = {"personas/alvaro-mur"}

def is_index(slug: str) -> bool:
    return slug.split("/")[-1].startswith("_index")

def main() -> None:
    # slug = ruta relativa sin .md, p.ej. "personas/erika-riepl"
    nodes: set[str] = set()
    outlinks: dict[str, set[str]] = {}
    for md in sorted(ARTICULOS.rglob("*.md")):
        slug = str(md.relative_to(ARTICULOS).with_suffix(""))
        nodes.add(slug)
        text = md.read_text(encoding="utf-8")
        targets = set()
        for m in WIKILINK.finditer(text):
            tgt = m.group(1).strip()
            if tgt and tgt != slug:
                targets.add(tgt)
        outlinks[slug] = targets

    # in-degree (backlinks): cuántos artículos distintos apuntan a cada nodo
    backlinks: Counter = Counter()
    for src, tgts in outlinks.items():
        for t in tgts:
            backlinks[t] += 1

    # co-ocurrencia: por cada artículo, todos los pares de sus outlinks
    # (excluyendo hubs e _index) cuentan +1 — "citados juntos por un tercero"
    cooc: Counter = Counter()
    for src, tgts in outlinks.items():
        clean = sorted(
            t for t in tgts
            if t not in EXCLUDE and not is_index(t) and t in nodes
        )
        for a, b in combinations(clean, 2):
            cooc[(a, b)] += 1

    total_edges = sum(len(t) for t in outlinks.values())
    print(f"# Reporte de enriquecimiento — grafo de wikilinks\n")
    print(f"Nodos (artículos):        {len(nodes)}")
    print(f"Aristas (wikilinks):      {total_edges}")
    print(f"Nodos con backlinks:      {len(backlinks)}\n")

    print("## Top 25 backlinks (in-degree) — los imanes de 'Relacionados'\n")
    for slug, n in backlinks.most_common(25):
        flag = "  ⚠ROTA" if slug not in nodes else ""
        print(f"{n:4}  {slug}{flag}")

    print("\n## Top 30 pares por co-ocurrencia — 'relaciones frecuentes'\n")
    for (a, b), n in cooc.most_common(30):
        print(f"{n:4}  {a}  ✕  {b}")

if __name__ == "__main__":
    main()
