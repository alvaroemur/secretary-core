#!/usr/bin/env python3
"""Validate the byte ceiling and compact handoff fields."""
from __future__ import annotations

import argparse
from pathlib import Path


MAX_BYTES = 4096
REQUIRED_MARKERS = (
    "plan:",
    "node:",
    "branch:",
    "worktree:",
    "PR:",
    "## Done",
    "## Decisions",
    "## Pending",
    "## Blockers",
    "## Verify first",
)


def validate(path: Path) -> list[str]:
    payload = path.read_bytes()
    errors: list[str] = []
    if len(payload) > MAX_BYTES:
        errors.append(f"{len(payload)} bytes exceeds the {MAX_BYTES}-byte limit")
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        return ["file is not valid UTF-8", *errors]
    missing = [marker for marker in REQUIRED_MARKERS if marker not in text]
    if missing:
        errors.append(f"missing required markers: {', '.join(missing)}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("brief", type=Path)
    args = parser.parse_args()
    errors = validate(args.brief)
    if errors:
        for error in errors:
            print(f"error: {error}")
        return 1
    print(f"ok: {args.brief} ({len(args.brief.read_bytes())} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
