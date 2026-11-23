#!/usr/bin/env python3
"""Stamp ``freshness.last_success_at`` in a module contract after a successful run.

Usage: stamp-freshness.py <contract.yaml> [--at ISO8601]

Rewrites only that one line, keeping the rest of the file byte for byte. The old
value may be quoted, unquoted or ``null``. Without ``--at`` it uses the current
local time with its UTC offset. Exits 1 when the contract has no
``last_success_at`` key, so a routine notices instead of reporting a stale module.
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

LINE_RE = re.compile(r'^(?P<indent>\s*)last_success_at:[^\n#]*(?P<comment>#.*)?$', re.M)


def stamp(text: str, when: str) -> str:
    def repl(m: re.Match) -> str:
        comment = f"  {m.group('comment')}" if m.group("comment") else ""
        return f'{m.group("indent")}last_success_at: "{when}"{comment}'

    new, n = LINE_RE.subn(repl, text, count=1)
    if n == 0:
        raise KeyError("last_success_at")
    return new


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("contract", type=Path)
    ap.add_argument("--at", help="ISO8601 timestamp (default: now, local offset)")
    args = ap.parse_args(argv)
    when = args.at or datetime.now().astimezone().isoformat(timespec="seconds")
    try:
        args.contract.write_text(stamp(args.contract.read_text(encoding="utf-8"), when), encoding="utf-8")
    except (OSError, KeyError) as exc:
        print(f"stamp-freshness: {args.contract}: {exc}", file=sys.stderr)
        return 1
    print(f"stamp-freshness: {args.contract} last_success_at={when}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
