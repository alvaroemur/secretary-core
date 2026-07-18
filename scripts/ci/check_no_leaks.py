#!/usr/bin/env python3
"""CI leak-guard: fail if any sensitive `redact` pattern survives in tracked files.

Reads the anonymization map (``secretary/data/export_examples_map.yml``) — the same
source of truth the exporter uses — and scans every git-TRACKED text file for the
``redact`` patterns/regexes. If a sensitive literal or match is found in committed
content, the guard exits non-zero and prints where.

`preserve` acts as an allowlist: a `redact` hit that falls entirely inside a preserved
public string (e.g. the shared engine repo `alvaroemur/secretary-core`) is ignored.

Excluded from the scan:
  - the map file itself (it legitimately contains the literals, as the redact source);
  - this guard script.

Run: ``python scripts/ci/check_no_leaks.py`` (exit 0 = clean).
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
MAP_REL = "secretary/data/export_examples_map.yml"
SELF_REL = "scripts/ci/check_no_leaks.py"

# Files that legitimately hold the raw literals and must be exempt from the scan.
EXEMPT = {MAP_REL, SELF_REL}


def _load_rules() -> tuple[list[dict[str, Any]], list[str]]:
    data = yaml.safe_load((REPO_ROOT / MAP_REL).read_text(encoding="utf-8")) or {}
    return (data.get("redact") or []), [str(x) for x in (data.get("preserve") or [])]


def _tracked_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [line for line in out.splitlines() if line and line not in EXEMPT]


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, ValueError, OSError):
        return None  # binary or unreadable — skip


def _match_spans(rule: dict[str, Any], line: str) -> list[tuple[int, int, str]]:
    """Return (start, end, matched_text) for every hit of a rule on a line."""
    spans: list[tuple[int, int, str]] = []
    if rule.get("regex"):
        for m in re.finditer(rule["regex"], line):
            spans.append((m.start(), m.end(), m.group(0)))
    elif rule.get("pattern"):
        pat = rule["pattern"]
        start = line.find(pat)
        while start != -1:
            spans.append((start, start + len(pat), pat))
            start = line.find(pat, start + 1)
    return spans


def _inside_preserved(line: str, start: int, end: int, preserve: list[str]) -> bool:
    """True if the [start,end) span sits entirely inside a preserved literal."""
    for keep in preserve:
        idx = line.find(keep)
        while idx != -1:
            if idx <= start and end <= idx + len(keep):
                return True
            idx = line.find(keep, idx + 1)
    return False


def main() -> int:
    redact, preserve = _load_rules()
    leaks: list[str] = []

    for rel in _tracked_files():
        text = _read_text(REPO_ROOT / rel)
        if text is None:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            for rule in redact:
                label = rule.get("pattern") or rule.get("regex")
                for start, end, matched in _match_spans(rule, line):
                    if _inside_preserved(line, start, end, preserve):
                        continue
                    leaks.append(f"{rel}:{lineno}: `{matched}` (regla: {label})")

    if leaks:
        print("LEAK GUARD: se encontraron literales sensibles en archivos trackeados:\n")
        for leak in leaks:
            print(f"  {leak}")
        print(
            f"\n{len(leaks)} hallazgo(s). Redactá con el mapa "
            f"({MAP_REL}) o agregá a `preserve` si es público."
        )
        return 1

    print("LEAK GUARD: OK — sin literales sensibles en archivos trackeados.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
