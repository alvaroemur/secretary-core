#!/usr/bin/env python3
"""CI leak-guard: fail if PII / sensitive literals leak into git-tracked files.

Detection is designed to work on a FRESH CLONE (CI), with no access to the private
secrets file:

- GENERIC `detect` regexes from the committed public map
  (``secretary/data/export_examples_map.yml``): any email, Google-Drive-style folder
  id, and phone number. These catch accidental PII without needing the real values.
- The `preserve` allowlist from the same map: public strings and the placeholder
  values redaction produces (e.g. `alvaroemur/secretary-core`, `Álvaro`,
  `your.personal.email@gmail.com`). A `detect` hit that sits inside a preserved
  string is ignored.

When the PRIVATE secrets file (``export_examples_secrets.yml``, gitignored) IS
present locally, the guard ALSO scans for those exact literals for precision.

Skipped: the public map, the committed template, this script, dependency lock files
(machine-generated hashes, not PII), and binary/unreadable files.

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
TEMPLATE_REL = "export_examples_secrets.example.yml"
SECRETS_REL = "export_examples_secrets.yml"
SELF_REL = "scripts/ci/check_no_leaks.py"

# Files exempt from scanning: they legitimately hold literals/patterns, or are
# machine-generated dependency manifests full of hash-like tokens.
EXEMPT_FILES = {MAP_REL, TEMPLATE_REL, SECRETS_REL, SELF_REL}
LOCKFILE_NAMES = {
    "uv.lock",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "poetry.lock",
    "Cargo.lock",
    "composer.lock",
    "Gemfile.lock",
}


def _load_map() -> dict[str, Any]:
    return yaml.safe_load((REPO_ROOT / MAP_REL).read_text(encoding="utf-8")) or {}


def _load_secret_literals() -> list[str]:
    """Exact `pattern` literals from the private secrets file (empty if absent)."""
    path = REPO_ROOT / SECRETS_REL
    if not path.is_file():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return [r["pattern"] for r in (data.get("redact") or []) if r.get("pattern")]


def _tracked_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    files = []
    for line in out.splitlines():
        if not line or line in EXEMPT_FILES:
            continue
        if Path(line).name in LOCKFILE_NAMES:
            continue
        files.append(line)
    return files


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, ValueError, OSError):
        return None  # binary or unreadable — skip


def _inside_preserved(line: str, start: int, end: int, preserve: list[str]) -> bool:
    """True if [start,end) sits entirely inside an occurrence of a preserved string."""
    for keep in preserve:
        idx = line.find(keep)
        while idx != -1:
            if idx <= start and end <= idx + len(keep):
                return True
            idx = line.find(keep, idx + 1)
    return False


def main() -> int:
    data = _load_map()
    preserve = [str(x) for x in (data.get("preserve") or [])]
    detectors: list[tuple[str, re.Pattern[str]]] = [
        (d.get("regex", ""), re.compile(d["regex"]))
        for d in (data.get("detect") or [])
        if d.get("regex")
    ]
    secret_literals = _load_secret_literals()

    leaks: list[str] = []
    for rel in _tracked_files():
        text = _read_text(REPO_ROOT / rel)
        if text is None:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            # Generic detectors (work without the private file).
            for label, pat in detectors:
                for m in pat.finditer(line):
                    if _inside_preserved(line, m.start(), m.end(), preserve):
                        continue
                    leaks.append(f"{rel}:{lineno}: `{m.group(0)}` (detect: {label})")
            # Exact private literals (only when the secrets file is present).
            for lit in secret_literals:
                start = line.find(lit)
                while start != -1:
                    if not _inside_preserved(line, start, start + len(lit), preserve):
                        leaks.append(f"{rel}:{lineno}: `{lit}` (literal privado)")
                    start = line.find(lit, start + 1)

    mode = "con archivo privado" if secret_literals else "solo regex genéricas (CI)"
    if leaks:
        print(f"LEAK GUARD [{mode}]: literales sensibles en archivos trackeados:\n")
        for leak in leaks:
            print(f"  {leak}")
        print(
            f"\n{len(leaks)} hallazgo(s). Redactá vía el mapa/secrets de "
            "export-examples, o agregá a `preserve` si es público."
        )
        return 1

    print(f"LEAK GUARD [{mode}]: OK — sin literales sensibles en archivos trackeados.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
