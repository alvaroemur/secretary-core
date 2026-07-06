"""Operator portal — aggregate live-data snapshot (spec 019 FR-4)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from secretary.config import instance_root


def aggregate_script() -> Path:
    return instance_root() / "scripts" / "portal" / "aggregate.py"


def run_aggregate(
    *,
    output: str | None = None,
    stdout: bool = False,
    validate_only: str | None = None,
    serve: bool = False,
    port: int = 8765,
) -> int:
    """Invoke instance aggregator script with SECRETARY_INSTANCE cwd."""
    script = aggregate_script()
    if not script.is_file():
        raise FileNotFoundError(f"No existe {script}")

    cmd: list[str] = [sys.executable, str(script)]
    if validate_only:
        cmd.extend(["--validate-only", validate_only])
    elif serve:
        cmd.extend(["--serve", "--port", str(port)])
    elif stdout:
        cmd.append("--stdout")
    elif output:
        cmd.extend(["--output", output])

    return subprocess.run(cmd, cwd=str(instance_root())).returncode
