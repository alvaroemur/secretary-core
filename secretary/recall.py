"""Deterministic memory search for sec-recall step 0."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from secretary.config import all_resolved_paths, instance_root, load_config

SKIP_DIRS = {".git", ".obsidian", "__pycache__", "node_modules", "output"}
MAX_SNIPPET = 240
MAX_RESULTS = 40


@dataclass
class RecallHit:
    source: str
    path: str
    kind: str
    score: int
    line: int | None
    snippet: str

    def to_dict(self) -> dict:
        return asdict(self)


def _tokenize(query: str) -> list[str]:
    return [t for t in re.split(r"\W+", query.lower()) if len(t) >= 2]


def _score_match(query: str, tokens: list[str], path: Path, text: str) -> tuple[int, int | None, str]:
    q = query.lower()
    name = path.name.lower()
    score = 0
    line_no: int | None = None
    snippet = ""

    if q in name:
        score += 80
    for tok in tokens:
        if tok in name:
            score += 30

    lines = text.splitlines()
    for i, line in enumerate(lines, start=1):
        low = line.lower()
        if q in low:
            score += 20
            if line_no is None:
                line_no = i
                snippet = line.strip()[:MAX_SNIPPET]
        else:
            for tok in tokens:
                if tok in low:
                    score += 5
                    if line_no is None:
                        line_no = i
                        snippet = line.strip()[:MAX_SNIPPET]

    if not snippet and text.strip():
        snippet = text.strip()[:MAX_SNIPPET]

    return score, line_no, snippet


def _kind_for(path: Path, roots: dict[str, Path]) -> str:
    p = str(path)
    for key, root in roots.items():
        if p.startswith(str(root)):
            return key.split(".")[0]
    if "heartbeat" in p:
        return "heartbeat"
    if "articulos" in p:
        return "wiki"
    return "memory"


def _iter_search_files() -> list[Path]:
    files: set[Path] = set()
    inst = instance_root()
    cfg = load_config()
    resolved = all_resolved_paths(cfg)

    wiki = resolved.get("wiki.articles")
    if wiki and wiki.is_dir():
        files.update(wiki.rglob("*.md"))

    for key, root in resolved.items():
        if not key.endswith(".memory") or not root.is_dir():
            continue
        for p in root.rglob("*"):
            if p.is_file() and p.suffix in {".md", ".txt"}:
                files.add(p)

    hb = resolved.get("operations.heartbeat")
    if hb and hb.is_dir():
        latest = hb / "latest.md"
        if latest.is_file():
            files.add(latest)
        for p in sorted(hb.glob("*.md"), reverse=True)[:3]:
            if p.name != "latest.md":
                files.add(p)

    # acciones.md often lives beside memory/
    for acc in inst.glob("extractores/*/memory/acciones.md"):
        files.add(acc)

    return list(files)


def search(query: str, limit: int = MAX_RESULTS) -> list[RecallHit]:
    tokens = _tokenize(query)
    if not query.strip():
        return []

    roots = all_resolved_paths()
    hits: list[RecallHit] = []

    for path in _iter_search_files():
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        score, line_no, snippet = _score_match(query, tokens, path, text)
        if score <= 0:
            continue

        inst = instance_root()
        try:
            rel = path.relative_to(inst)
        except ValueError:
            rel = path
        hits.append(
            RecallHit(
                source=str(rel),
                path=str(path),
                kind=_kind_for(path, roots),
                score=score,
                line=line_no,
                snippet=snippet,
            )
        )

    hits.sort(key=lambda h: (-h.score, h.source))
    return hits[:limit]


def format_table(hits: list[RecallHit]):
    from rich.table import Table
    from rich.markup import escape

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("score", justify="right", width=6, style="dim")
    table.add_column("kind", width=12, style="magenta")
    table.add_column("source", style="green")
    table.add_column("snippet")

    for h in hits:
        raw_snippet = h.snippet.replace("\n", " ")[:140]
        table.add_row(str(h.score), h.kind, h.source, escape(raw_snippet))

    return table


def format_json(hits: list[RecallHit]) -> str:
    return json.dumps([h.to_dict() for h in hits], ensure_ascii=False, indent=2)
