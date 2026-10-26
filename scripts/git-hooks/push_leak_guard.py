#!/usr/bin/env python3
"""pre-push leak guard: block pushes of sensitive literals to PUBLIC GitHub repos.

Runs from the global hooks dispatcher (``hook-dispatch``) for every push. It does
nothing unless the destination is a public GitHub repository. For public repos it
scans the lines the push adds with the same rules as the CI guard
(``secretary/data/leak_guard.yml``), the optional private literals
(``leak_guard_secrets.yml``) and the slugs of the owner's private repositories.

Visibility and the private repo list come from ``gh`` and are cached for a day.
Without ``gh`` or network the guard warns and lets the push through: CI is still
the second line of defence.

Bypass for a single push: ``git push --no-verify``.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Iterator, Optional

import yaml

CORE_ROOT = Path(__file__).resolve().parents[2]
MAP_PATH = CORE_ROOT / "secretary/data/leak_guard.yml"
SECRET_PATHS = (CORE_ROOT / "leak_guard_secrets.yml", CORE_ROOT / "export_examples_secrets.yml")
# Files that legitimately hold the patterns themselves (only inside the core repo).
EXEMPT_FILES = {
    "secretary/data/leak_guard.yml",
    "leak_guard_secrets.example.yml",
    "leak_guard_secrets.yml",
    "export_examples_secrets.yml",
    "scripts/ci/check_no_leaks.py",
    "scripts/git-hooks/push_leak_guard.py",
}
CACHE_TTL = 24 * 3600
ZERO_SHA = "0" * 40
SLUG_RE = re.compile(r"github\.com[:/]([^/\s]+)/([^/\s]+?)(?:\.git)?/?$")


def cache_path() -> Path:
    base = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    return base / "secretary" / "push-guard.json"


def load_cache() -> dict[str, Any]:
    try:
        return json.loads(cache_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_cache(cache: dict[str, Any]) -> None:
    path = cache_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cache, indent=1), encoding="utf-8")
    except OSError:
        pass


def cached(cache: dict[str, Any], key: str, fetch: Any) -> Any:
    entry = cache.get(key)
    if entry and time.time() - entry.get("at", 0) < CACHE_TTL:
        return entry["value"]
    value = fetch()
    if value is not None:
        cache[key] = {"at": time.time(), "value": value}
    return value


def gh_json(args: list[str]) -> Any:
    try:
        out = subprocess.run(["gh", *args], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None
    try:
        return json.loads(out.stdout)
    except ValueError:
        return None


def repo_slug(url: str) -> Optional[str]:
    m = SLUG_RE.search(url.strip())
    return f"{m.group(1)}/{m.group(2)}" if m else None


def visibility(slug: str, cache: dict[str, Any]) -> Optional[str]:
    def fetch() -> Optional[str]:
        data = gh_json(["repo", "view", slug, "--json", "visibility"])
        return data.get("visibility") if data else None

    return cached(cache, f"visibility:{slug}", fetch)


def private_slugs(owner: str, cache: dict[str, Any]) -> list[str]:
    def fetch() -> Optional[list[str]]:
        data = gh_json(
            ["repo", "list", owner, "--visibility", "private", "--limit", "1000", "--json", "nameWithOwner"]
        )
        return [r["nameWithOwner"] for r in data] if data is not None else None

    return cached(cache, f"private:{owner}", fetch) or []


def load_rules(private: list[str]) -> tuple[list[tuple[str, re.Pattern[str]]], list[str]]:
    """Detectors (label, regex) and preserve allowlist."""
    data = yaml.safe_load(MAP_PATH.read_text(encoding="utf-8")) or {}
    preserve = [str(x) for x in (data.get("preserve") or [])]
    detectors = [
        ("detect", re.compile(d["regex"])) for d in (data.get("detect") or []) if d.get("regex")
    ]
    for path in SECRET_PATHS:
        if path.is_file():
            secrets = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            literals = [str(x) for x in (secrets.get("literals") or [])]
            literals += [r["pattern"] for r in (secrets.get("redact") or []) if r.get("pattern")]
            detectors += [("literal privado", re.compile(re.escape(lit))) for lit in literals]
            break
    for slug in private:
        name = slug.split("/", 1)[1]
        detectors.append(("repo privado", re.compile(re.escape(slug))))
        detectors.append(("repo privado", re.compile(rf"\b{re.escape(name)}#\d+")))
    return detectors, preserve


def inside_preserved(line: str, start: int, end: int, preserve: list[str]) -> bool:
    for keep in preserve:
        idx = line.find(keep)
        while idx != -1:
            if idx <= start and end <= idx + len(keep):
                return True
            idx = line.find(keep, idx + 1)
    return False


def added_lines(rev_args: list[str]) -> Iterator[tuple[str, str]]:
    """(file, line) for every line the given commits add."""
    out = subprocess.run(
        ["git", "log", "-p", "--no-color", "--no-ext-diff", "--format=", *rev_args],
        capture_output=True,
        text=True,
        errors="replace",
    ).stdout
    current = ""
    for line in out.splitlines():
        if line.startswith("+++ "):
            current = line[6:] if line.startswith("+++ b/") else ""
        elif line.startswith("+") and current:
            yield current, line[1:]


def scan(rev_args: list[str], detectors: list[tuple[str, re.Pattern[str]]], preserve: list[str]) -> list[str]:
    hits = []
    for path, line in added_lines(rev_args):
        if path in EXEMPT_FILES:
            continue
        for label, pat in detectors:
            for m in pat.finditer(line):
                if not inside_preserved(line, m.start(), m.end(), preserve):
                    hits.append(f"{path}: `{m.group(0)}` ({label})")
    return sorted(set(hits))


def push_ranges(stdin: str, remote: str) -> list[list[str]]:
    """git log arguments for the commits each pushed ref adds."""
    ranges = []
    for row in stdin.splitlines():
        parts = row.split()
        if len(parts) != 4:
            continue
        _local_ref, local_sha, _remote_ref, remote_sha = parts
        if local_sha == ZERO_SHA:
            continue  # branch deletion: nothing is published
        if remote_sha == ZERO_SHA:
            ranges.append([local_sha, "--not", f"--remotes={remote}"])
        else:
            ranges.append([f"{remote_sha}..{local_sha}"])
    return ranges


def main(argv: list[str]) -> int:
    remote = argv[1] if len(argv) > 1 else "origin"
    url = argv[2] if len(argv) > 2 else remote
    slug = repo_slug(url)
    if not slug:
        return 0
    cache = load_cache()
    vis = visibility(slug, cache)
    if vis is None:
        print(f"[push-guard] aviso: no pude leer la visibilidad de {slug} (gh); push sin revisar.", file=sys.stderr)
        save_cache(cache)
        return 0
    if vis != "PUBLIC":
        save_cache(cache)
        return 0
    detectors, preserve = load_rules(private_slugs(slug.split("/")[0], cache))
    save_cache(cache)
    hits = []
    for rev_args in push_ranges(sys.stdin.read(), remote):
        hits += scan(rev_args, detectors, preserve)
    if not hits:
        return 0
    print(f"[push-guard] {slug} es PÚBLICO y el push agrega datos sensibles:\n", file=sys.stderr)
    for hit in sorted(set(hits)):
        print(f"  {hit}", file=sys.stderr)
    print(
        "\nQuita esas líneas del commit (o agrega a `preserve` en leak_guard.yml si son públicas)."
        "\nPara saltar la revisión en un push puntual: git push --no-verify",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
