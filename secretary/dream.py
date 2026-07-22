"""Wrapper for the instance's sec-dream deterministic collector (spec 020 FR-19).

`scripts/dream/collect.py` lives in the instance (data/config side), not in this
package — it reads instance-specific paths via `.secretary.yml`. This module just
resolves that script and shells out to it, the same pattern used for
`routines setup`'s `install-routine-schedule.sh`.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from secretary.config import instance_root


def run_collect(write_collect: bool = False) -> int:
    """Invoke the instance's scripts/dream/collect.py, forwarding stdout/stderr."""
    script = instance_root() / "scripts" / "dream" / "collect.py"
    if not script.is_file():
        print(f"dream collect: no existe {script}", file=sys.stderr)
        return 2

    cmd = [sys.executable, str(script)]
    if write_collect:
        cmd.append("--write-collect")

    result = subprocess.run(cmd)
    return result.returncode


def run_emit_metrics(since: str | None = None, dry_run: bool = False) -> int:
    """Append this sec-dream run to the routines ledger (issue #24 / spec 019).

    sec-dream runs natively as a Claude Code scheduled task — it has no
    invoke-*.sh subprocess/JSONL stream for `parse-routine-metrics.py` to
    parse, so it can't emit forward the way api-cron/cursor-cron do. Instead
    of reimplementing session-transcript parsing here, shell out to the
    instance's `backfill-metrics-claude-sessions.py`, scoped to routine
    `sec-dream` and today — it already knows how to read Claude session
    transcripts (marker `<scheduled-task name="sec-dream">`) and is
    idempotent on `session_id`/`run_id`.
    """
    script = instance_root() / "scripts" / "routines" / "backfill-metrics-claude-sessions.py"
    if not script.is_file():
        print(f"dream emit-metrics: no existe {script}", file=sys.stderr)
        return 2

    if since is None:
        since = datetime.now(ZoneInfo("America/Lima")).date().isoformat()

    cmd = [sys.executable, str(script), "--since", since, "--routine", "sec-dream"]
    if dry_run:
        cmd.append("--dry-run")

    result = subprocess.run(cmd)
    return result.returncode
