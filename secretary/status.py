"""Persist task progress to the daily brief (replaces sec-status.sh)."""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path

from secretary.config import load_config

DEFAULT_BRIEF_REPO = "alvaroemur/cowork-secretary"
DEFAULT_BRIEF_LABEL = "tipo:informe-diario"


def _brief_target() -> tuple[str, str]:
    cfg = load_config()
    brief = cfg.get("brief") or {}
    repo = brief.get("repo") or DEFAULT_BRIEF_REPO
    label = brief.get("label") or DEFAULT_BRIEF_LABEL
    return str(repo), str(label)
SIGNATURE = Path.home() / ".claude" / "scripts" / "sec-signature.sh"
HAPTIC = Path.home() / ".claude" / "scripts" / "sec-haptic.sh"


def _signature_mark() -> str:
    if SIGNATURE.is_file():
        return subprocess.check_output(
            [str(SIGNATURE), "sec-status", "--mark"],
            text=True,
        ).strip()
    return "<!-- agent-generated:sec-status runtime=cli -->"


def _open_brief_issue() -> int:
    brief_repo, brief_label = _brief_target()
    raw = subprocess.check_output(
        [
            "gh",
            "issue",
            "list",
            "--repo",
            brief_repo,
            "--label",
            brief_label,
            "--state",
            "open",
            "--json",
            "number,createdAt",
        ],
        text=True,
    )
    issues = json.loads(raw)
    if not issues:
        raise RuntimeError(
            "no hay brief abierto (informe-diario) — no se persistió el avance"
        )
    issues.sort(key=lambda i: i["createdAt"])
    return int(issues[-1]["number"])


def post_status(emoji: str, ref: str, note: str) -> tuple[int, str]:
    """Comment on today's brief. Returns (issue_number, summary line)."""
    issue = _open_brief_issue()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    ref_part = f"{ref} " if ref else ""
    body = f"{_signature_mark()}\nsec-status · {now} · {emoji} {ref_part}— {note}"

    brief_repo, _ = _brief_target()
    subprocess.run(
        ["gh", "issue", "comment", str(issue), "--repo", brief_repo, "--body", body],
        check=True,
        stdout=subprocess.DEVNULL,
    )

    if HAPTIC.is_file() and os.access(HAPTIC, os.X_OK):
        env = os.environ.copy()
        env["SEC_HAPTIC_SRC"] = "sec-status"
        subprocess.Popen(
            [str(HAPTIC), "detecto"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
        )

    summary = f"✓ persistido en brief #{issue}: {emoji} {ref_part}— {note}"
    return issue, summary
