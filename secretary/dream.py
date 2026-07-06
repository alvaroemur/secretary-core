"""Wrapper for the instance's sec-dream deterministic collector (spec 020 FR-19).

`scripts/dream/collect.py` lives in the instance (data/config side), not in this
package — it reads instance-specific paths via `.secretary.yml`. This module just
resolves that script and shells out to it, the same pattern used for
`routines setup`'s `install-routine-schedule.sh`.
"""

from __future__ import annotations

import subprocess
import sys

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
